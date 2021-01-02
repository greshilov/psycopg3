"""
psycopg3 types package
"""

# Copyright (C) 2020 The Psycopg Team

from ..oids import builtins, INVALID_OID
from ..proto import AdaptContext

# Register default adapters
from . import array, composite
from . import range

# Wrapper objects
from .numeric import Int2, Int4, Int8, Oid
from .json import Json, Jsonb
from .range import Range, Int4Range, Int8Range, DecimalRange
from .range import DateRange, DateTimeRange, DateTimeTZRange

# Supper objects
from .range import RangeInfo
from .composite import CompositeInfo

# Adapter objects
from .text import (
    StringDumper,
    StringBinaryDumper,
    TextLoader,
    TextBinaryLoader,
    BytesDumper,
    BytesBinaryDumper,
    ByteaLoader,
    ByteaBinaryLoader,
)
from .numeric import (
    IntDumper,
    FloatDumper,
    FloatBinaryDumper,
    DecimalDumper,
    Int2Dumper,
    Int4Dumper,
    Int8Dumper,
    OidDumper,
    Int2BinaryDumper,
    Int4BinaryDumper,
    Int8BinaryDumper,
    OidBinaryDumper,
    IntLoader,
    Int2BinaryLoader,
    Int4BinaryLoader,
    Int8BinaryLoader,
    OidBinaryLoader,
    FloatLoader,
    Float4BinaryLoader,
    Float8BinaryLoader,
    NumericLoader,
)
from .singletons import (
    BoolDumper,
    BoolBinaryDumper,
    NoneDumper,
    BoolLoader,
    BoolBinaryLoader,
)
from .date import (
    DateDumper,
    TimeDumper,
    DateTimeDumper,
    TimeDeltaDumper,
    DateLoader,
    TimeLoader,
    TimeTzLoader,
    TimestampLoader,
    TimestamptzLoader,
    IntervalLoader,
)
from .json import (
    JsonDumper,
    JsonBinaryDumper,
    JsonbDumper,
    JsonbBinaryDumper,
    JsonLoader,
    JsonBinaryLoader,
    JsonbBinaryLoader,
)
from .uuid import (
    UUIDDumper,
    UUIDBinaryDumper,
    UUIDLoader,
    UUIDBinaryLoader,
)
from .network import (
    InterfaceDumper,
    NetworkDumper,
    InetLoader,
    CidrLoader,
)
from .range import (
    RangeDumper,
    Int4RangeDumper,
    Int8RangeDumper,
    NumRangeDumper,
    DateRangeDumper,
    TimestampRangeDumper,
    TimestampTZRangeDumper,
    RangeLoader,
    Int4RangeLoader,
    Int8RangeLoader,
    NumericRangeLoader,
    DateRangeLoader,
    TimestampRangeLoader,
    TimestampTZRangeLoader,
)
from .array import (
    ListDumper,
    ListBinaryDumper,
)
from .composite import (
    TupleDumper,
    RecordLoader,
    RecordBinaryLoader,
    CompositeLoader,
    CompositeBinaryLoader,
)


def register_default_globals(ctx: AdaptContext) -> None:
    StringDumper.register(str, ctx)
    StringBinaryDumper.register(str, ctx)
    TextLoader.register(INVALID_OID, ctx)
    TextLoader.register("bpchar", ctx)
    TextLoader.register("name", ctx)
    TextLoader.register("text", ctx)
    TextLoader.register("varchar", ctx)
    TextBinaryLoader.register("bpchar", ctx)
    TextBinaryLoader.register("name", ctx)
    TextBinaryLoader.register("text", ctx)
    TextBinaryLoader.register("varchar", ctx)

    BytesDumper.register(bytes, ctx)
    BytesDumper.register(bytearray, ctx)
    BytesDumper.register(memoryview, ctx)
    BytesBinaryDumper.register(bytes, ctx)
    BytesBinaryDumper.register(bytearray, ctx)
    BytesBinaryDumper.register(memoryview, ctx)
    ByteaLoader.register("bytea", ctx)
    ByteaBinaryLoader.register(INVALID_OID, ctx)
    ByteaBinaryLoader.register("bytea", ctx)

    IntDumper.register(int, ctx)
    FloatDumper.register(float, ctx)
    Int8BinaryDumper.register(int, ctx)
    FloatBinaryDumper.register(float, ctx)
    DecimalDumper.register("decimal.Decimal", ctx)
    Int2Dumper.register(Int2, ctx)
    Int4Dumper.register(Int4, ctx)
    Int8Dumper.register(Int8, ctx)
    OidDumper.register(Oid, ctx)
    Int2BinaryDumper.register(Int2, ctx)
    Int4BinaryDumper.register(Int4, ctx)
    Int8BinaryDumper.register(Int8, ctx)
    OidBinaryDumper.register(Oid, ctx)
    IntLoader.register("int2")
    IntLoader.register("int4")
    IntLoader.register("int8")
    IntLoader.register("oid")
    Int2BinaryLoader.register("int2")
    Int4BinaryLoader.register("int4")
    Int8BinaryLoader.register("int8")
    OidBinaryLoader.register("oid")
    FloatLoader.register("float4")
    FloatLoader.register("float8")
    Float4BinaryLoader.register("float4")
    Float8BinaryLoader.register("float8")
    NumericLoader.register("numeric")

    BoolDumper.register(bool, ctx)
    BoolBinaryDumper.register(bool, ctx)
    NoneDumper.register(type(None), ctx)
    BoolLoader.register("bool", ctx)
    BoolBinaryLoader.register("bool", ctx)

    DateDumper.register("datetime.date", ctx)
    TimeDumper.register("datetime.time", ctx)
    DateTimeDumper.register("datetime.datetime", ctx)
    TimeDeltaDumper.register("datetime.timedelta", ctx)
    DateLoader.register("date", ctx)
    TimeLoader.register("time", ctx)
    TimeTzLoader.register("timetz", ctx)
    TimestampLoader.register("timestamp", ctx)
    TimestamptzLoader.register("timestamptz", ctx)
    IntervalLoader.register("interval", ctx)

    JsonDumper.register(Json, ctx)
    JsonBinaryDumper.register(Json, ctx)
    JsonbDumper.register(Jsonb, ctx)
    JsonbBinaryDumper.register(Jsonb, ctx)
    JsonLoader.register("json", ctx)
    JsonLoader.register("jsonb", ctx)
    JsonBinaryLoader.register("json", ctx)
    JsonbBinaryLoader.register("jsonb", ctx)

    UUIDDumper.register("uuid.UUID", ctx)
    UUIDBinaryDumper.register("uuid.UUID", ctx)
    UUIDLoader.register("uuid", ctx)
    UUIDBinaryLoader.register("uuid", ctx)

    InterfaceDumper.register("ipaddress.IPv4Address", ctx)
    InterfaceDumper.register("ipaddress.IPv6Address", ctx)
    InterfaceDumper.register("ipaddress.IPv4Interface", ctx)
    InterfaceDumper.register("ipaddress.IPv6Interface", ctx)
    NetworkDumper.register("ipaddress.IPv4Network", ctx)
    NetworkDumper.register("ipaddress.IPv6Network", ctx)
    InetLoader.register("inet", ctx)
    CidrLoader.register("cidr", ctx)

    Int4RangeDumper.register(Int4Range, ctx)
    Int8RangeDumper.register(Int8Range, ctx)
    NumRangeDumper.register(DecimalRange, ctx)
    DateRangeDumper.register(DateRange, ctx)
    TimestampRangeDumper.register(DateTimeRange, ctx)
    TimestampTZRangeDumper.register(DateTimeTZRange, ctx)
    Int4RangeLoader.register("int4range", ctx)
    Int8RangeLoader.register("int8range", ctx)
    NumericRangeLoader.register("numrange", ctx)
    DateRangeLoader.register("daterange", ctx)
    TimestampRangeLoader.register("tsrange", ctx)
    TimestampTZRangeLoader.register("tstzrange", ctx)

    ListDumper.register(list, ctx)
    ListBinaryDumper.register(list, ctx)

    TupleDumper.register(tuple, ctx)
    RecordLoader.register("record", ctx)
    RecordBinaryLoader.register("record", ctx)

    array.register_all_arrays()
