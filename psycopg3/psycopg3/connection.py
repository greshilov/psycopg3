"""
psycopg3 connection objects
"""

# Copyright (C) 2020 The Psycopg Team

import sys
import asyncio
import logging
import warnings
import threading
from types import TracebackType
from typing import Any, AsyncIterator, Callable, Iterator, List, NamedTuple
from typing import Optional, Type, TYPE_CHECKING
from weakref import ref, ReferenceType
from functools import partial
from contextlib import contextmanager

if sys.version_info >= (3, 7):
    from contextlib import asynccontextmanager
else:
    from .utils.context import asynccontextmanager

from . import pq
from . import adapt
from . import cursor
from . import errors as e
from . import waiting
from . import encodings
from .pq import ConnStatus, ExecStatus, TransactionStatus, Format
from .sql import Composable
from .proto import PQGen, PQGenConn, RV, Query, Params, AdaptContext
from .proto import ConnectionType
from .conninfo import make_conninfo
from .generators import notifies
from .transaction import Transaction, AsyncTransaction
from ._preparing import PrepareManager

logger = logging.getLogger(__name__)
package_logger = logging.getLogger("psycopg3")

connect: Callable[[str], PQGenConn["PGconn"]]
execute: Callable[["PGconn"], PQGen[List["PGresult"]]]

if TYPE_CHECKING:
    from .cursor import AsyncCursor, BaseCursor, Cursor
    from .pq.proto import PGconn, PGresult

if pq.__impl__ == "c":
    from psycopg3_c import _psycopg3

    connect = _psycopg3.connect
    execute = _psycopg3.execute

else:
    from . import generators

    connect = generators.connect
    execute = generators.execute


class Notify(NamedTuple):
    """An asynchronous notification received from the database."""

    channel: str
    """The name of the channel on which the notification was received."""

    payload: str
    """The message attached to the notification."""

    pid: int
    """The PID of the backend process which sent the notification."""


Notify.__module__ = "psycopg3"

NoticeHandler = Callable[[e.Diagnostic], None]
NotifyHandler = Callable[[Notify], None]


class BaseConnection(AdaptContext):
    """
    Base class for different types of connections.

    Share common functionalities such as access to the wrapped PGconn, but
    allow different interfaces (sync/async).
    """

    # DBAPI2 exposed exceptions
    Warning = e.Warning
    Error = e.Error
    InterfaceError = e.InterfaceError
    DatabaseError = e.DatabaseError
    DataError = e.DataError
    OperationalError = e.OperationalError
    IntegrityError = e.IntegrityError
    InternalError = e.InternalError
    ProgrammingError = e.ProgrammingError
    NotSupportedError = e.NotSupportedError

    # Enums useful for the connection
    ConnStatus = pq.ConnStatus
    TransactionStatus = pq.TransactionStatus

    cursor_factory: Type["BaseCursor[Any]"]

    def __init__(self, pgconn: "PGconn"):
        self.pgconn = pgconn  # TODO: document this
        self._autocommit = False
        self._adapters = adapt.AdaptersMap(adapt.global_adapters)
        self._notice_handlers: List[NoticeHandler] = []
        self._notify_handlers: List[NotifyHandler] = []

        # Stack of savepoint names managed by current transaction blocks.
        # the first item is "" in case the outermost Transaction must manage
        # only a begin/commit and not a savepoint.
        self._savepoints: List[str] = []

        self._prepared: PrepareManager = PrepareManager()

        wself = ref(self)

        pgconn.notice_handler = partial(BaseConnection._notice_handler, wself)
        pgconn.notify_handler = partial(BaseConnection._notify_handler, wself)

    def __del__(self) -> None:
        # If fails on connection we might not have this attribute yet
        if not hasattr(self, "pgconn"):
            return

        status = self.pgconn.transaction_status
        if status == TransactionStatus.UNKNOWN:
            return

        status = TransactionStatus(status)
        warnings.warn(
            f"connection {self} was deleted while still open."
            f" Please use 'with' or '.close()' to close the connection",
            ResourceWarning,
        )

    def __repr__(self) -> str:
        cls = f"{self.__class__.__module__}.{self.__class__.__qualname__}"
        info = pq.misc.connection_summary(self.pgconn)
        return f"<{cls} {info} at 0x{id(self):x}>"

    @property
    def closed(self) -> bool:
        """`True` if the connection is closed."""
        return self.pgconn.status == ConnStatus.BAD

    @property
    def autocommit(self) -> bool:
        """The autocommit state of the connection."""
        return self._autocommit

    @autocommit.setter
    def autocommit(self, value: bool) -> None:
        self._set_autocommit(value)

    def _set_autocommit(self, value: bool) -> None:
        # Base implementation, not thread safe
        # subclasses must call it holding a lock
        status = self.pgconn.transaction_status
        if status != TransactionStatus.IDLE:
            if self._savepoints:
                raise e.ProgrammingError(
                    "couldn't change autocommit state: "
                    "connection.transaction() context in progress"
                )
            else:
                raise e.ProgrammingError(
                    "couldn't change autocommit state: "
                    "connection in transaction status "
                    f"{TransactionStatus(status).name}"
                )

        self._autocommit = value

    @property
    def client_encoding(self) -> str:
        """The Python codec name of the connection's client encoding."""
        pgenc = self.pgconn.parameter_status(b"client_encoding") or b"UTF8"
        return encodings.pg2py(pgenc)

    @client_encoding.setter
    def client_encoding(self, name: str) -> None:
        self._set_client_encoding(name)

    def _set_client_encoding(self, name: str) -> None:
        raise NotImplementedError

    def _set_client_encoding_gen(self, name: str) -> PQGen[None]:
        self.pgconn.send_query_params(
            b"select set_config('client_encoding', $1, false)",
            [encodings.py2pg(name)],
        )
        (result,) = yield from execute(self.pgconn)
        if result.status != ExecStatus.TUPLES_OK:
            raise e.error_from_result(result, encoding=self.client_encoding)

    @property
    def adapters(self) -> adapt.AdaptersMap:
        return self._adapters

    @property
    def connection(self) -> "BaseConnection":
        # implement the AdaptContext protocol
        return self

    def cancel(self) -> None:
        """Cancel the current operation on the connection."""
        c = self.pgconn.get_cancel()
        c.cancel()

    def add_notice_handler(self, callback: NoticeHandler) -> None:
        """
        Register a callable to be invoked when a notice message is received.
        """
        self._notice_handlers.append(callback)

    def remove_notice_handler(self, callback: NoticeHandler) -> None:
        """
        Unregister a notice message callable previously registered.
        """
        self._notice_handlers.remove(callback)

    @staticmethod
    def _notice_handler(
        wself: "ReferenceType[BaseConnection]", res: "PGresult"
    ) -> None:
        self = wself()
        if not (self and self._notice_handler):
            return

        diag = e.Diagnostic(res, self.client_encoding)
        for cb in self._notice_handlers:
            try:
                cb(diag)
            except Exception as ex:
                package_logger.exception(
                    "error processing notice callback '%s': %s", cb, ex
                )

    def add_notify_handler(self, callback: NotifyHandler) -> None:
        """
        Register a callable to be invoked whenever a notification is received.
        """
        self._notify_handlers.append(callback)

    def remove_notify_handler(self, callback: NotifyHandler) -> None:
        """
        Unregister a notification callable previously registered.
        """
        self._notify_handlers.remove(callback)

    @staticmethod
    def _notify_handler(
        wself: "ReferenceType[BaseConnection]", pgn: pq.PGnotify
    ) -> None:
        self = wself()
        if not (self and self._notify_handlers):
            return

        enc = self.client_encoding
        n = Notify(pgn.relname.decode(enc), pgn.extra.decode(enc), pgn.be_pid)
        for cb in self._notify_handlers:
            cb(n)

    @property
    def prepare_threshold(self) -> Optional[int]:
        """
        Number of times a query is executed before it is prepared.

        - If it is set to 0, every query is prepared the first time is
          executed.
        - If it is set to `!None`, prepared statements are disabled on the
          connection.

        Default value: 5
        """
        return self._prepared.prepare_threshold

    @prepare_threshold.setter
    def prepare_threshold(self, value: Optional[int]) -> None:
        self._prepared.prepare_threshold = value

    @property
    def prepared_max(self) -> int:
        """
        Maximum number of prepared statements on the connection.

        Default value: 100
        """
        return self._prepared.prepared_max

    @prepared_max.setter
    def prepared_max(self, value: int) -> None:
        self._prepared.prepared_max = value

    # Generators to perform high-level operations on the connection
    #
    # These operations are expressed in terms of non-blocking generators
    # and the task of waiting when needed (when the generators yield) is left
    # to the connections subclass, which might wait either in blocking mode
    # or through asyncio.
    #
    # All these generators assume exclusive acces to the connection: subclasses
    # should have a lock and hold it before calling and consuming them.

    @classmethod
    def _connect_gen(
        cls: Type[ConnectionType],
        conninfo: str = "",
        *,
        autocommit: bool = False,
        **kwargs: Any,
    ) -> PQGenConn[ConnectionType]:
        """Generator to connect to the database and create a new instance."""
        conninfo = make_conninfo(conninfo, **kwargs)
        pgconn = yield from connect(conninfo)
        conn = cls(pgconn)
        conn._autocommit = autocommit
        return conn

    def _exec_command(self, command: Query) -> PQGen[None]:
        """
        Generator to send a command and receive the result to the backend.

        Only used to implement internal commands such as commit, returning
        no result. The cursor can do more complex stuff.
        """
        if self.pgconn.status != ConnStatus.OK:
            if self.pgconn.status == ConnStatus.BAD:
                raise e.OperationalError("the connection is closed")
            raise e.InterfaceError(
                f"cannot execute operations: the connection is"
                f" in status {self.pgconn.status}"
            )

        if isinstance(command, str):
            command = command.encode(self.client_encoding)
        elif isinstance(command, Composable):
            command = command.as_bytes(self)

        self.pgconn.send_query(command)
        result = (yield from execute(self.pgconn))[-1]
        if result.status != ExecStatus.COMMAND_OK:
            if result.status == ExecStatus.FATAL_ERROR:
                raise e.error_from_result(
                    result, encoding=self.client_encoding
                )
            else:
                raise e.InterfaceError(
                    f"unexpected result {ExecStatus(result.status).name}"
                    f" from command {command.decode('utf8')!r}"
                )

    def _start_query(self) -> PQGen[None]:
        """Generator to start a transaction if necessary."""
        if self._autocommit:
            return

        if self.pgconn.transaction_status != TransactionStatus.IDLE:
            return

        yield from self._exec_command(b"begin")

    def _commit_gen(self) -> PQGen[None]:
        """Generator implementing `Connection.commit()`."""
        if self._savepoints:
            raise e.ProgrammingError(
                "Explicit commit() forbidden within a Transaction "
                "context. (Transaction will be automatically committed "
                "on successful exit from context.)"
            )
        if self.pgconn.transaction_status == TransactionStatus.IDLE:
            return

        yield from self._exec_command(b"commit")

    def _rollback_gen(self) -> PQGen[None]:
        """Generator implementing `Connection.rollback()`."""
        if self._savepoints:
            raise e.ProgrammingError(
                "Explicit rollback() forbidden within a Transaction "
                "context. (Either raise Rollback() or allow "
                "an exception to propagate out of the context.)"
            )
        if self.pgconn.transaction_status == TransactionStatus.IDLE:
            return

        yield from self._exec_command(b"rollback")


class Connection(BaseConnection):
    """
    Wrapper for a connection to the database.
    """

    __module__ = "psycopg3"

    cursor_factory: Type["Cursor"]

    def __init__(self, pgconn: "PGconn"):
        super().__init__(pgconn)
        self.lock = threading.Lock()
        self.cursor_factory = cursor.Cursor

    @classmethod
    def connect(
        cls, conninfo: str = "", *, autocommit: bool = False, **kwargs: Any
    ) -> "Connection":
        """
        Connect to a database server and return a new `Connection` instance.

        TODO: connection_timeout to be implemented.
        """
        return cls._wait_conn(
            cls._connect_gen(conninfo, autocommit=autocommit, **kwargs)
        )

    def __enter__(self) -> "Connection":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if exc_type:
            self.rollback()
        else:
            self.commit()

        self.close()

    def close(self) -> None:
        """Close the database connection."""
        self.pgconn.finish()

    def cursor(self, name: str = "", format: Format = Format.TEXT) -> "Cursor":
        """
        Return a new `Cursor` to send commands and queries to the connection.
        """
        if name:
            raise NotImplementedError

        return self.cursor_factory(self, format=format)

    def execute(
        self,
        query: Query,
        params: Optional[Params] = None,
        prepare: Optional[bool] = None,
    ) -> "Cursor":
        """Execute a query and return a cursor to read its results."""
        cur = self.cursor()
        return cur.execute(query, params, prepare=prepare)

    def commit(self) -> None:
        """Commit any pending transaction to the database."""
        with self.lock:
            self.wait(self._commit_gen())

    def rollback(self) -> None:
        """Roll back to the start of any pending transaction."""
        with self.lock:
            self.wait(self._rollback_gen())

    @contextmanager
    def transaction(
        self,
        savepoint_name: Optional[str] = None,
        force_rollback: bool = False,
    ) -> Iterator[Transaction]:
        """
        Start a context block with a new transaction or nested transaction.

        :param savepoint_name: Name of the savepoint used to manage a nested
            transaction. If `!None`, one will be chosen automatically.
        :param force_rollback: Roll back the transaction at the end of the
            block even if there were no error (e.g. to try a no-op process).
        """
        with Transaction(self, savepoint_name, force_rollback) as tx:
            yield tx

    def notifies(self) -> Iterator[Notify]:
        """
        Yield `Notify` objects as soon as they are received from the database.
        """
        while 1:
            with self.lock:
                ns = self.wait(notifies(self.pgconn))
            enc = self.client_encoding
            for pgn in ns:
                n = Notify(
                    pgn.relname.decode(enc), pgn.extra.decode(enc), pgn.be_pid
                )
                yield n

    def wait(self, gen: PQGen[RV], timeout: Optional[float] = 0.1) -> RV:
        """
        Consume a generator operating on the connection.

        The function must be used on generators that don't change connection
        fd (i.e. not on connect and reset).
        """
        return waiting.wait(gen, self.pgconn.socket, timeout=timeout)

    @classmethod
    def _wait_conn(
        cls, gen: PQGenConn[RV], timeout: Optional[float] = 0.1
    ) -> RV:
        """Consume a connection generator."""
        return waiting.wait_conn(gen, timeout=timeout)

    def _set_autocommit(self, value: bool) -> None:
        with self.lock:
            super()._set_autocommit(value)

    def _set_client_encoding(self, name: str) -> None:
        with self.lock:
            self.wait(self._set_client_encoding_gen(name))


class AsyncConnection(BaseConnection):
    """
    Asynchronous wrapper for a connection to the database.
    """

    __module__ = "psycopg3"

    cursor_factory: Type["AsyncCursor"]

    def __init__(self, pgconn: "PGconn"):
        super().__init__(pgconn)
        self.lock = asyncio.Lock()
        self.cursor_factory = cursor.AsyncCursor

    @classmethod
    async def connect(
        cls, conninfo: str = "", *, autocommit: bool = False, **kwargs: Any
    ) -> "AsyncConnection":
        return await cls._wait_conn(
            cls._connect_gen(conninfo, autocommit=autocommit, **kwargs)
        )

    async def __aenter__(self) -> "AsyncConnection":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if exc_type:
            await self.rollback()
        else:
            await self.commit()

        await self.close()

    async def close(self) -> None:
        self.pgconn.finish()

    async def cursor(
        self, name: str = "", format: Format = Format.TEXT
    ) -> "AsyncCursor":
        """
        Return a new `AsyncCursor` to send commands and queries to the connection.
        """
        if name:
            raise NotImplementedError

        return self.cursor_factory(self, format=format)

    async def execute(
        self,
        query: Query,
        params: Optional[Params] = None,
        prepare: Optional[bool] = None,
    ) -> "AsyncCursor":
        cur = await self.cursor()
        return await cur.execute(query, params, prepare=prepare)

    async def commit(self) -> None:
        async with self.lock:
            await self.wait(self._commit_gen())

    async def rollback(self) -> None:
        async with self.lock:
            await self.wait(self._rollback_gen())

    @asynccontextmanager
    async def transaction(
        self,
        savepoint_name: Optional[str] = None,
        force_rollback: bool = False,
    ) -> AsyncIterator[AsyncTransaction]:
        """
        Start a context block with a new transaction or nested transaction.
        """
        tx = AsyncTransaction(self, savepoint_name, force_rollback)
        async with tx:
            yield tx

    async def notifies(self) -> AsyncIterator[Notify]:
        while 1:
            async with self.lock:
                ns = await self.wait(notifies(self.pgconn))
            enc = self.client_encoding
            for pgn in ns:
                n = Notify(
                    pgn.relname.decode(enc), pgn.extra.decode(enc), pgn.be_pid
                )
                yield n

    async def wait(self, gen: PQGen[RV]) -> RV:
        return await waiting.wait_async(gen, self.pgconn.socket)

    @classmethod
    async def _wait_conn(cls, gen: PQGenConn[RV]) -> RV:
        return await waiting.wait_conn_async(gen)

    def _set_client_encoding(self, name: str) -> None:
        raise AttributeError(
            "'client_encoding' is read-only on async connections:"
            " please use await .set_client_encoding() instead."
        )

    async def set_client_encoding(self, name: str) -> None:
        """Async version of the `~Connection.client_encoding` setter."""
        async with self.lock:
            await self.wait(self._set_client_encoding_gen(name))

    def _set_autocommit(self, value: bool) -> None:
        raise AttributeError(
            "autocommit is read-only on async connections:"
            " please use await connection.set_autocommit() instead."
            " Note that you can pass an 'autocommit' value to 'connect()'"
            " if it doesn't need to change during the connection's lifetime."
        )

    async def set_autocommit(self, value: bool) -> None:
        """Async version of the `~Connection.autocommit` setter."""
        async with self.lock:
            super()._set_autocommit(value)
