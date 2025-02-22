import sys
import ipaddress
import subprocess as sp

import pytest

from psycopg3.adapt import Format


@pytest.mark.parametrize("fmt_in", [Format.TEXT, Format.BINARY])
@pytest.mark.parametrize("val", ["192.168.0.1", "2001:db8::"])
def test_address_dump(conn, fmt_in, val):
    binary_check(fmt_in)
    ph = "%s" if fmt_in == Format.TEXT else "%b"
    cur = conn.cursor()
    cur.execute(f"select {ph} = %s::inet", (ipaddress.ip_address(val), val))
    assert cur.fetchone()[0] is True
    cur.execute(
        f"select {ph} = array[null, %s]::inet[]",
        ([None, ipaddress.ip_interface(val)], val),
    )
    assert cur.fetchone()[0] is True


@pytest.mark.parametrize("fmt_in", [Format.TEXT, Format.BINARY])
@pytest.mark.parametrize("val", ["127.0.0.1/24", "::ffff:102:300/128"])
def test_interface_dump(conn, fmt_in, val):
    binary_check(fmt_in)
    ph = "%s" if fmt_in == Format.TEXT else "%b"
    cur = conn.cursor()
    cur.execute(f"select {ph} = %s::inet", (ipaddress.ip_interface(val), val))
    assert cur.fetchone()[0] is True
    cur.execute(
        f"select {ph} = array[null, %s]::inet[]",
        ([None, ipaddress.ip_interface(val)], val),
    )
    assert cur.fetchone()[0] is True


@pytest.mark.parametrize("fmt_in", [Format.TEXT, Format.BINARY])
@pytest.mark.parametrize("val", ["127.0.0.0/24", "::ffff:102:300/128"])
def test_network_dump(conn, fmt_in, val):
    binary_check(fmt_in)
    ph = "%s" if fmt_in == Format.TEXT else "%b"
    cur = conn.cursor()
    cur.execute(f"select {ph} = %s::cidr", (ipaddress.ip_network(val), val))
    assert cur.fetchone()[0] is True
    cur.execute(
        f"select {ph} = array[NULL, %s]::cidr[]",
        ([None, ipaddress.ip_network(val)], val),
    )
    assert cur.fetchone()[0] is True


@pytest.mark.parametrize("fmt_out", [Format.TEXT, Format.BINARY])
@pytest.mark.parametrize("val", ["127.0.0.1/32", "::ffff:102:300/128"])
def test_inet_load_address(conn, fmt_out, val):
    binary_check(fmt_out)
    cur = conn.cursor(format=fmt_out)
    cur.execute("select %s::inet", (val,))
    addr = ipaddress.ip_address(val.split("/", 1)[0])
    assert cur.fetchone()[0] == addr
    cur.execute("select array[null, %s::inet]", (val,))
    assert cur.fetchone()[0] == [None, addr]


@pytest.mark.parametrize("fmt_out", [Format.TEXT, Format.BINARY])
@pytest.mark.parametrize("val", ["127.0.0.1/24", "::ffff:102:300/127"])
def test_inet_load_network(conn, fmt_out, val):
    binary_check(fmt_out)
    cur = conn.cursor(format=fmt_out)
    cur.execute("select %s::inet", (val,))
    assert cur.fetchone()[0] == ipaddress.ip_interface(val)
    cur.execute("select array[null, %s::inet]", (val,))
    assert cur.fetchone()[0] == [None, ipaddress.ip_interface(val)]


@pytest.mark.parametrize("fmt_out", [Format.TEXT, Format.BINARY])
@pytest.mark.parametrize("val", ["127.0.0.0/24", "::ffff:102:300/128"])
def test_cidr_load(conn, fmt_out, val):
    binary_check(fmt_out)
    cur = conn.cursor(format=fmt_out)
    cur.execute("select %s::cidr", (val,))
    assert cur.fetchone()[0] == ipaddress.ip_network(val)
    cur.execute("select array[null, %s::cidr]", (val,))
    assert cur.fetchone()[0] == [None, ipaddress.ip_network(val)]


def binary_check(fmt):
    if fmt == Format.BINARY:
        pytest.xfail("inet binary not implemented")


@pytest.mark.subprocess
def test_lazy_load(dsn):
    script = f"""\
import sys
import psycopg3

# In 3.6 it seems already loaded (at least on Travis).
if sys.version_info >= (3, 7):
    assert 'ipaddress' not in sys.modules

conn = psycopg3.connect({dsn!r})
with conn.cursor() as cur:
    cur.execute("select '127.0.0.1'::inet")
    cur.fetchone()

conn.close()
assert 'ipaddress' in sys.modules
"""

    sp.check_call([sys.executable, "-s", "-c", script])
