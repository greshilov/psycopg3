"""
Utility module to manipulate queries
"""

# Copyright (C) 2020 The Psycopg Team

import re
from typing import Any, Dict, List, Mapping, Match, NamedTuple, Optional
from typing import Sequence, Tuple, Union, TYPE_CHECKING
from functools import lru_cache

from . import errors as e
from .pq import Format
from .sql import Composable
from .proto import Query, Params

if TYPE_CHECKING:
    from .proto import Transformer


class QueryPart(NamedTuple):
    pre: bytes
    item: Union[int, str]
    format: Format


class PostgresQuery:
    """
    Helper to convert a Python query and parameters into Postgres format.
    """

    __slots__ = """
        params types formats
        _tx _unknown_oid _parts query _encoding _order
        """.split()

    def __init__(self, transformer: "Transformer"):
        self._tx = transformer

        self.params: Optional[List[Optional[bytes]]] = None
        # these are tuples so they can be used as keys e.g. in prepared stmts
        self.types: Tuple[int, ...] = ()
        self.formats: Optional[List[Format]] = None

        self._parts: List[QueryPart]
        self.query = b""
        self._encoding = "utf-8"
        self._order: Optional[List[str]] = None

        conn = transformer.connection
        if conn:
            self._encoding = conn.client_encoding

    def convert(self, query: Query, vars: Optional[Params]) -> None:
        """
        Set up the query and parameters to convert.

        The results of this function can be obtained accessing the object
        attributes (`query`, `params`, `types`, `formats`).
        """
        if isinstance(query, Composable):
            query = query.as_bytes(self._tx)

        if vars is not None:
            self.query, self.formats, self._order, self._parts = _query2pg(
                query, self._encoding
            )
        else:
            if isinstance(query, str):
                query = query.encode(self._encoding)
            self.query = query
            self.formats = self._order = None

        self.dump(vars)

    def dump(self, vars: Optional[Params]) -> None:
        """
        Process a new set of variables on the same query as before.

        This method updates `params` and `types`.
        """
        if vars is not None:
            params = _validate_and_reorder_params(
                self._parts, vars, self._order
            )
            assert self.formats is not None
            self.params, self.types = self._tx.dump_sequence(
                params, self.formats
            )
        else:
            self.params = None
            self.types = ()


@lru_cache()
def _query2pg(
    query: Union[bytes, str], encoding: str
) -> Tuple[bytes, List[Format], Optional[List[str]], List[QueryPart]]:
    """
    Convert Python query and params into something Postgres understands.

    - Convert Python placeholders (``%s``, ``%(name)s``) into Postgres
      format (``$1``, ``$2``)
    - placeholders can be %s or %b (text or binary)
    - return ``query`` (bytes), ``formats`` (list of formats) ``order``
      (sequence of names used in the query, in the position they appear)
      ``parts`` (splits of queries and placeholders).
    """
    if isinstance(query, str):
        query = query.encode(encoding)
    if not isinstance(query, bytes):
        # encoding from str already happened
        raise TypeError(
            f"the query should be str or bytes,"
            f" got {type(query).__name__} instead"
        )

    parts = _split_query(query, encoding)
    order: Optional[List[str]] = None
    chunks: List[bytes] = []
    formats = []

    if isinstance(parts[0].item, int):
        for part in parts[:-1]:
            assert isinstance(part.item, int)
            chunks.append(part.pre)
            chunks.append(b"$%d" % (part.item + 1))
            formats.append(part.format)

    elif isinstance(parts[0].item, str):
        seen: Dict[str, Tuple[bytes, Format]] = {}
        order = []
        for part in parts[:-1]:
            assert isinstance(part.item, str)
            chunks.append(part.pre)
            if part.item not in seen:
                ph = b"$%d" % (len(seen) + 1)
                seen[part.item] = (ph, part.format)
                order.append(part.item)
                chunks.append(ph)
                formats.append(part.format)
            else:
                if seen[part.item][1] != part.format:
                    raise e.ProgrammingError(
                        f"placeholder '{part.item}' cannot have"
                        f" different formats"
                    )
                chunks.append(seen[part.item][0])

    # last part
    chunks.append(parts[-1].pre)

    return b"".join(chunks), formats, order, parts


def _validate_and_reorder_params(
    parts: List[QueryPart], vars: Params, order: Optional[List[str]]
) -> Sequence[Any]:
    """
    Verify the compatibility between a query and a set of params.
    """
    # Try concrete types, then abstract types
    t = type(vars)
    if t is list or t is tuple:
        sequence = True
    elif t is dict:
        sequence = False
    elif isinstance(vars, Sequence) and not isinstance(vars, (bytes, str)):
        sequence = True
    elif isinstance(vars, Mapping):
        sequence = False
    else:
        raise TypeError(
            f"query parameters should be a sequence or a mapping,"
            f" got {type(vars).__name__}"
        )

    if sequence:
        if len(vars) != len(parts) - 1:
            raise e.ProgrammingError(
                f"the query has {len(parts) - 1} placeholders but"
                f" {len(vars)} parameters were passed"
            )
        if vars and not isinstance(parts[0].item, int):
            raise TypeError(
                "named placeholders require a mapping of parameters"
            )
        return vars  # type: ignore[return-value]

    else:
        if vars and len(parts) > 1 and not isinstance(parts[0][1], str):
            raise TypeError(
                "positional placeholders (%s) require a sequence of parameters"
            )
        try:
            return [
                vars[item] for item in order or ()  # type: ignore[call-overload]
            ]
        except KeyError:
            raise e.ProgrammingError(
                f"query parameter missing:"
                f" {', '.join(sorted(i for i in order or () if i not in vars))}"
            )


_re_placeholder = re.compile(
    rb"""(?x)
        %                       # a literal %
        (?:
            (?:
                \( ([^)]+) \)   # or a name in (braces)
                .               # followed by a format
            )
            |
            (?:.)               # or any char, really
        )
        """
)


def _split_query(query: bytes, encoding: str = "ascii") -> List[QueryPart]:
    parts: List[Tuple[bytes, Optional[Match[bytes]]]] = []
    cur = 0

    # pairs [(fragment, match], with the last match None
    m = None
    for m in _re_placeholder.finditer(query):
        pre = query[cur : m.span(0)[0]]
        parts.append((pre, m))
        cur = m.span(0)[1]
    if m:
        parts.append((query[cur:], None))
    else:
        parts.append((query, None))

    rv = []

    # drop the "%%", validate
    i = 0
    phtype = None
    while i < len(parts):
        pre, m = parts[i]
        if m is None:
            # last part
            rv.append(QueryPart(pre, 0, Format.TEXT))
            break

        ph = m.group(0)
        if ph == b"%%":
            # unescape '%%' to '%' and merge the parts
            pre1, m1 = parts[i + 1]
            parts[i + 1] = (pre + b"%" + pre1, m1)
            del parts[i]
            continue

        if ph == b"%(":
            raise e.ProgrammingError(
                f"incomplete placeholder:"
                f" '{query[m.span(0)[0]:].split()[0].decode(encoding)}'"
            )
        elif ph == b"% ":
            # explicit messasge for a typical error
            raise e.ProgrammingError(
                "incomplete placeholder: '%'; if you want to use '%' as an"
                " operator you can double it up, i.e. use '%%'"
            )
        elif ph[-1:] not in b"bs":
            raise e.ProgrammingError(
                f"only '%s' and '%b' placeholders allowed, got"
                f" {m.group(0).decode(encoding)}"
            )

        # Index or name
        item: Union[int, str]
        item = m.group(1).decode(encoding) if m.group(1) else i

        if not phtype:
            phtype = type(item)
        elif phtype is not type(item):
            raise e.ProgrammingError(
                "positional and named placeholders cannot be mixed"
            )

        # Binary format
        format = Format(ph[-1:] == b"b")

        rv.append(QueryPart(pre, item, format))
        i += 1

    return rv
