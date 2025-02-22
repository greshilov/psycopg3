"""
Adapers for numeric types.
"""

# Copyright (C) 2020 The Psycopg Team

import struct
from typing import Any, Callable, Dict, Tuple, cast
from decimal import Decimal

from ..oids import builtins
from ..adapt import Dumper, Loader, Format

_PackInt = Callable[[int], bytes]
_PackFloat = Callable[[float], bytes]
_UnpackInt = Callable[[bytes], Tuple[int]]
_UnpackFloat = Callable[[bytes], Tuple[float]]

_pack_int2 = cast(_PackInt, struct.Struct("!h").pack)
_pack_int4 = cast(_PackInt, struct.Struct("!i").pack)
_pack_uint4 = cast(_PackInt, struct.Struct("!I").pack)
_pack_int8 = cast(_PackInt, struct.Struct("!q").pack)
_pack_float8 = cast(_PackFloat, struct.Struct("!d").pack)
_unpack_int2 = cast(_UnpackInt, struct.Struct("!h").unpack)
_unpack_int4 = cast(_UnpackInt, struct.Struct("!i").unpack)
_unpack_uint4 = cast(_UnpackInt, struct.Struct("!I").unpack)
_unpack_int8 = cast(_UnpackInt, struct.Struct("!q").unpack)
_unpack_float4 = cast(_UnpackFloat, struct.Struct("!f").unpack)
_unpack_float8 = cast(_UnpackFloat, struct.Struct("!d").unpack)


# Wrappers to force numbers to be cast as specific PostgreSQL types


class Int2(int):
    def __new__(cls, arg: int) -> "Int2":
        return super().__new__(cls, arg)  # type: ignore


class Int4(int):
    def __new__(cls, arg: int) -> "Int4":
        return super().__new__(cls, arg)  # type: ignore


class Int8(int):
    def __new__(cls, arg: int) -> "Int8":
        return super().__new__(cls, arg)  # type: ignore


class Oid(int):
    def __new__(cls, arg: int) -> "Oid":
        return super().__new__(cls, arg)  # type: ignore


class NumberDumper(Dumper):

    format = Format.TEXT

    def dump(self, obj: Any) -> bytes:
        return str(obj).encode("utf8")

    def quote(self, obj: Any) -> bytes:
        value = self.dump(obj)
        return value if obj >= 0 else b" " + value


class SpecialValuesDumper(NumberDumper):

    _special: Dict[bytes, bytes] = {}

    def quote(self, obj: Any) -> bytes:
        value = self.dump(obj)

        if value in self._special:
            return self._special[value]

        return value if obj >= 0 else b" " + value


class IntDumper(NumberDumper):
    _oid = builtins["int8"].oid


class FloatDumper(SpecialValuesDumper):

    format = Format.TEXT
    _oid = builtins["float8"].oid

    _special = {
        b"inf": b"'Infinity'::float8",
        b"-inf": b"'-Infinity'::float8",
        b"nan": b"'NaN'::float8",
    }


class FloatBinaryDumper(Dumper):

    format = Format.BINARY
    _oid = builtins["float8"].oid

    def dump(self, obj: float) -> bytes:
        return _pack_float8(obj)


class DecimalDumper(SpecialValuesDumper):

    _oid = builtins["numeric"].oid

    _special = {
        b"Infinity": b"'Infinity'::numeric",
        b"-Infinity": b"'-Infinity'::numeric",
        b"NaN": b"'NaN'::numeric",
    }


class Int2Dumper(NumberDumper):
    _oid = builtins["int2"].oid


class Int4Dumper(NumberDumper):
    _oid = builtins["int4"].oid


class Int8Dumper(NumberDumper):
    _oid = builtins["int8"].oid


class OidDumper(NumberDumper):
    _oid = builtins["oid"].oid


class Int2BinaryDumper(Int2Dumper):

    format = Format.BINARY

    def dump(self, obj: int) -> bytes:
        return _pack_int2(obj)


class Int4BinaryDumper(Int4Dumper):

    format = Format.BINARY

    def dump(self, obj: int) -> bytes:
        return _pack_int4(obj)


class Int8BinaryDumper(Int8Dumper):

    format = Format.BINARY

    def dump(self, obj: int) -> bytes:
        return _pack_int8(obj)


class OidBinaryDumper(OidDumper):

    format = Format.BINARY

    def dump(self, obj: int) -> bytes:
        return _pack_uint4(obj)


class IntLoader(Loader):

    format = Format.TEXT

    def load(self, data: bytes) -> int:
        # it supports bytes directly
        return int(data)


class Int2BinaryLoader(Loader):

    format = Format.BINARY

    def load(self, data: bytes) -> int:
        return _unpack_int2(data)[0]


class Int4BinaryLoader(Loader):

    format = Format.BINARY

    def load(self, data: bytes) -> int:
        return _unpack_int4(data)[0]


class Int8BinaryLoader(Loader):

    format = Format.BINARY

    def load(self, data: bytes) -> int:
        return _unpack_int8(data)[0]


class OidBinaryLoader(Loader):

    format = Format.BINARY

    def load(self, data: bytes) -> int:
        return _unpack_uint4(data)[0]


class FloatLoader(Loader):

    format = Format.TEXT

    def load(self, data: bytes) -> float:
        # it supports bytes directly
        return float(data)


class Float4BinaryLoader(Loader):

    format = Format.BINARY

    def load(self, data: bytes) -> float:
        return _unpack_float4(data)[0]


class Float8BinaryLoader(Loader):

    format = Format.BINARY

    def load(self, data: bytes) -> float:
        return _unpack_float8(data)[0]


class NumericLoader(Loader):

    format = Format.TEXT

    def load(self, data: bytes) -> Decimal:
        return Decimal(data.decode("utf8"))
