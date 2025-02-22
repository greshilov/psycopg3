"""
Maps of builtin types and names
"""

# Copyright (C) 2020 The Psycopg Team

from typing import Dict, Iterator, Optional, Union


class TypeInfo:
    def __init__(self, name: str, oid: int, array_oid: int):
        self.name = name
        self.oid = oid
        self.array_oid = array_oid

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__qualname__}:"
            f" {self.name} (oid: {self.oid}, array oid: {self.array_oid})>"
        )


class BuiltinTypeInfo(TypeInfo):
    def __init__(
        self,
        name: str,
        oid: int,
        array_oid: int,
        alt_name: str,
        delimiter: str,
    ):
        super().__init__(name, oid, array_oid)
        self.alt_name = alt_name
        self.delimiter = delimiter


class TypesRegistry:
    """
    Container for the information about types in a database.
    """

    def __init__(self) -> None:
        self._by_oid: Dict[int, TypeInfo] = {}
        self._by_name: Dict[str, TypeInfo] = {}

    def add(self, info: TypeInfo) -> None:
        self._by_oid[info.oid] = info
        if info.array_oid:
            self._by_oid[info.array_oid] = info
        self._by_name[info.name] = info

        if isinstance(info, BuiltinTypeInfo):
            if info.alt_name not in self._by_name:
                self._by_name[info.alt_name] = info

    def __iter__(self) -> Iterator[TypeInfo]:
        seen = set()
        for t in self._by_oid.values():
            if t.oid not in seen:
                seen.add(t.oid)
                yield t

    def __getitem__(self, key: Union[str, int]) -> TypeInfo:
        if isinstance(key, str):
            return self._by_name[key]
        elif isinstance(key, int):
            return self._by_oid[key]
        else:
            raise TypeError(
                f"the key must be an oid or a name, got {type(key)}"
            )

    def get(self, key: Union[str, int]) -> Optional[TypeInfo]:
        try:
            return self[key]
        except KeyError:
            return None


builtins = TypesRegistry()

# Use tools/update_oids.py to update this data.
for r in [
    # fmt: off
    # autogenerated: start

    # Generated from PostgreSQL 13.0

    ('aclitem', 1033, 1034, 'aclitem', ','),
    ('any', 2276, 0, '"any"', ','),
    ('anyarray', 2277, 0, 'anyarray', ','),
    ('anycompatible', 5077, 0, 'anycompatible', ','),
    ('anycompatiblearray', 5078, 0, 'anycompatiblearray', ','),
    ('anycompatiblenonarray', 5079, 0, 'anycompatiblenonarray', ','),
    ('anycompatiblerange', 5080, 0, 'anycompatiblerange', ','),
    ('anyelement', 2283, 0, 'anyelement', ','),
    ('anyenum', 3500, 0, 'anyenum', ','),
    ('anynonarray', 2776, 0, 'anynonarray', ','),
    ('anyrange', 3831, 0, 'anyrange', ','),
    ('bit', 1560, 1561, 'bit', ','),
    ('bool', 16, 1000, 'boolean', ','),
    ('box', 603, 1020, 'box', ';'),
    ('bpchar', 1042, 1014, 'character', ','),
    ('bytea', 17, 1001, 'bytea', ','),
    ('char', 18, 1002, '"char"', ','),
    ('cid', 29, 1012, 'cid', ','),
    ('cidr', 650, 651, 'cidr', ','),
    ('circle', 718, 719, 'circle', ','),
    ('cstring', 2275, 1263, 'cstring', ','),
    ('date', 1082, 1182, 'date', ','),
    ('daterange', 3912, 3913, 'daterange', ','),
    ('event_trigger', 3838, 0, 'event_trigger', ','),
    ('float4', 700, 1021, 'real', ','),
    ('float8', 701, 1022, 'double precision', ','),
    ('gtsvector', 3642, 3644, 'gtsvector', ','),
    ('inet', 869, 1041, 'inet', ','),
    ('int2', 21, 1005, 'smallint', ','),
    ('int2vector', 22, 1006, 'int2vector', ','),
    ('int4', 23, 1007, 'integer', ','),
    ('int4range', 3904, 3905, 'int4range', ','),
    ('int8', 20, 1016, 'bigint', ','),
    ('int8range', 3926, 3927, 'int8range', ','),
    ('internal', 2281, 0, 'internal', ','),
    ('interval', 1186, 1187, 'interval', ','),
    ('json', 114, 199, 'json', ','),
    ('jsonb', 3802, 3807, 'jsonb', ','),
    ('jsonpath', 4072, 4073, 'jsonpath', ','),
    ('line', 628, 629, 'line', ','),
    ('lseg', 601, 1018, 'lseg', ','),
    ('macaddr', 829, 1040, 'macaddr', ','),
    ('macaddr8', 774, 775, 'macaddr8', ','),
    ('money', 790, 791, 'money', ','),
    ('name', 19, 1003, 'name', ','),
    ('numeric', 1700, 1231, 'numeric', ','),
    ('numrange', 3906, 3907, 'numrange', ','),
    ('oid', 26, 1028, 'oid', ','),
    ('oidvector', 30, 1013, 'oidvector', ','),
    ('path', 602, 1019, 'path', ','),
    ('point', 600, 1017, 'point', ','),
    ('polygon', 604, 1027, 'polygon', ','),
    ('record', 2249, 2287, 'record', ','),
    ('refcursor', 1790, 2201, 'refcursor', ','),
    ('regclass', 2205, 2210, 'regclass', ','),
    ('regcollation', 4191, 4192, 'regcollation', ','),
    ('regconfig', 3734, 3735, 'regconfig', ','),
    ('regdictionary', 3769, 3770, 'regdictionary', ','),
    ('regnamespace', 4089, 4090, 'regnamespace', ','),
    ('regoper', 2203, 2208, 'regoper', ','),
    ('regoperator', 2204, 2209, 'regoperator', ','),
    ('regproc', 24, 1008, 'regproc', ','),
    ('regprocedure', 2202, 2207, 'regprocedure', ','),
    ('regrole', 4096, 4097, 'regrole', ','),
    ('regtype', 2206, 2211, 'regtype', ','),
    ('text', 25, 1009, 'text', ','),
    ('tid', 27, 1010, 'tid', ','),
    ('time', 1083, 1183, 'time without time zone', ','),
    ('timestamp', 1114, 1115, 'timestamp without time zone', ','),
    ('timestamptz', 1184, 1185, 'timestamp with time zone', ','),
    ('timetz', 1266, 1270, 'time with time zone', ','),
    ('trigger', 2279, 0, 'trigger', ','),
    ('tsquery', 3615, 3645, 'tsquery', ','),
    ('tsrange', 3908, 3909, 'tsrange', ','),
    ('tstzrange', 3910, 3911, 'tstzrange', ','),
    ('tsvector', 3614, 3643, 'tsvector', ','),
    ('txid_snapshot', 2970, 2949, 'txid_snapshot', ','),
    ('unknown', 705, 0, 'unknown', ','),
    ('uuid', 2950, 2951, 'uuid', ','),
    ('varbit', 1562, 1563, 'bit varying', ','),
    ('varchar', 1043, 1015, 'character varying', ','),
    ('void', 2278, 0, 'void', ','),
    ('xid', 28, 1011, 'xid', ','),
    ('xid8', 5069, 271, 'xid8', ','),
    ('xml', 142, 143, 'xml', ','),
    # autogenerated: end
    # fmt: on
]:
    builtins.add(BuiltinTypeInfo(*r))


# A few oids used a bit everywhere
INVALID_OID = 0
TEXT_OID = builtins["text"].oid
TEXT_ARRAY_OID = builtins["text"].array_oid
