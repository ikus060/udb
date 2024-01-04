# -*- coding: utf-8 -*-
# udb, A web interface to manage IT network
# Copyright (C) 2022 IKUS Software inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import ipaddress

from sqlalchemy import Boolean, String, TypeDecorator, event, func
from sqlalchemy.dialects.postgresql import CIDR, INET
from sqlalchemy.engine import Engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import GenericFunction


def _bytes_to_ip_network(value):
    if value[1] == 6:
        return ipaddress.ip_network(value[2:18]).supernet(new_prefix=int.from_bytes(value[18:], "big"))
    return ipaddress.ip_network(value[2:6]).supernet(new_prefix=int.from_bytes(value[6:], "big"))


def _ip_network_to_bytes(value):
    if value is None:
        return None
    if hasattr(value, 'network_address'):
        # IPNetwork
        return b'%s%s%s' % (
            value.version.to_bytes(2, byteorder='big'),
            value.network_address.packed,
            value.prefixlen.to_bytes(2, byteorder='big'),
        )
    # IPAddress
    return b'%s%s%s' % (
        value.version.to_bytes(2, byteorder='big'),
        value.packed,
        value.max_prefixlen.to_bytes(2, byteorder='big'),
    )


def _sqlite_inet(value):
    """
    Convert value into exploded ip_address.
    """
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    return _ip_network_to_bytes(ipaddress.ip_network(value, strict=False))


def _sqlite_host(value):
    """
    Return host value of inet or cidr.
    """
    if value is None:
        return None
    if isinstance(value, bytes):
        n = _bytes_to_ip_network(value)
    else:
        n = ipaddress.ip_network(value, strict=False)
    return n.network_address.compressed


def _sqlite_text(value):
    """
    Return text value of inet or cidr.
    """
    if value is None:
        return None
    if isinstance(value, bytes):
        n = _bytes_to_ip_network(value)
    else:
        n = ipaddress.ip_network(value, strict=False)
    return n.compressed


def _sqlite_broadcast(value):
    """
    Convert ip_network into comparable bytes.
    """
    if value is None:
        return None
    if isinstance(value, bytes):
        n = _bytes_to_ip_network(value)
    else:
        n = ipaddress.ip_network(value)
    return _ip_network_to_bytes(n.broadcast_address)


def _sqlite_family(value):
    """
    Receive inet, return integer
    """
    if value is None:
        return None
    if isinstance(value, bytes):
        return value[1]
    return ipaddress.ip_network(value, strict=False).version


def _sqlite_masklen(value):
    """
    Receive inet return marklen. masklen(inet '192.168.1.5/24') → 24
    """
    if value is None:
        return None
    if isinstance(value, bytes):
        n = _bytes_to_ip_network(value)
    else:
        n = ipaddress.ip_network(value)
    return n.prefixlen


def _sqlite_subnet_of(value, other):
    """
    Return True if this `value` network is a subnet of `other`.
    """
    if value is None or other is None:
        return False
    n = _bytes_to_ip_network(value) if isinstance(value, bytes) else ipaddress.ip_network(value)
    o = _bytes_to_ip_network(other) if isinstance(other, bytes) else ipaddress.ip_network(other)
    return n.version == o.version and n != o and n.subnet_of(o)


def _sqlite_subnet_of_or_equals(value, other):
    """
    Return True if this `value` network is a subnet of `other`.
    """
    if value is None or other is None:
        return False
    n = _bytes_to_ip_network(value) if isinstance(value, bytes) else ipaddress.ip_network(value)
    o = _bytes_to_ip_network(other) if isinstance(other, bytes) else ipaddress.ip_network(other)
    return n.version == o.version and n.subnet_of(o)


class subnet_of(GenericFunction):
    type = Boolean
    name = "subnet_of"
    inherit_cache = True


class subnet_of_or_equals(GenericFunction):
    type = Boolean
    name = "subnet_of_or_equals"
    inherit_cache = True


@compiles(subnet_of, "postgresql")
def _render_subnet_of_postgresql(element, compiler, **kw):
    """
    On Postgresql, `subnet_of` is implemented with operator '<<'.
    """
    left, right = element.clauses
    return "%s << %s" % (compiler.process(left, **kw), compiler.process(right, **kw))


@compiles(subnet_of_or_equals, "postgresql")
def _render_subnet_of_or_equals_postgresql(element, compiler, **kw):
    """
    On Postgresql, `subnet_of_or_equals` is implemented with operator '<<='.
    """
    left, right = element.clauses
    return "%s <<= %s" % (compiler.process(left, **kw), compiler.process(right, **kw))


@event.listens_for(Engine, "connect")
def _register_sqlite_cidr_functions(dbapi_con, unused):
    """
    On SQLite engine, register custom function to support CIDR operations.
    """
    if 'sqlite' in repr(dbapi_con):
        dbapi_con.create_function("broadcast", 1, _sqlite_broadcast, deterministic=True)
        dbapi_con.create_function("host", 1, _sqlite_host, deterministic=True)
        dbapi_con.create_function("inet", 1, _sqlite_inet, deterministic=True)
        dbapi_con.create_function("inet_sortable", 1, _sqlite_inet, deterministic=True)
        dbapi_con.create_function("family", 1, _sqlite_family, deterministic=True)
        dbapi_con.create_function("text", 1, _sqlite_text, deterministic=True)
        dbapi_con.create_function("masklen", 1, _sqlite_masklen, deterministic=True)
        dbapi_con.create_function("subnet_of", 2, _sqlite_subnet_of, deterministic=True)
        dbapi_con.create_function("subnet_of_or_equals", 2, _sqlite_subnet_of_or_equals, deterministic=True)


class CidrType(TypeDecorator):
    """
    Type decorator to store CIDR 192.168.0.0/24 in Postgresql database.
    In SQLite we store the value as string.
    """

    impl = CIDR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(CIDR())
        return dialect.type_descriptor(String())

    def process_bind_param(self, value, dialect):
        if value is None or value == '':
            return None
        if dialect.name == "postgresql":
            return value
        # SQlite convert to bytes
        if isinstance(value, bytes):
            return value
        n = ipaddress.ip_network(value)
        return _ip_network_to_bytes(n)

    def process_result_value(self, value, dialect):
        if value is None or value == '':
            return None
        if dialect.name == "postgresql":
            return value
        # SQlite convert from bytes
        return _bytes_to_ip_network(value).compressed

    class comparator_factory(String.Comparator):
        def host(self):
            return func.host(self)

        def text(self):
            return func.text(self)

        def inet(self):
            return func.inet(self)

        def family(self):
            return func.family(self)

        def broadcast(self):
            return func.broadcast(self)


class InetType(TypeDecorator):
    """
    Type decorator to store INET 192.168.0.1/24 in Postgresql database.
    In SQLite we store the value as string.
    """

    impl = INET
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(INET())
        return dialect.type_descriptor(String())

    def process_bind_param(self, value, dialect):
        if value is None or value == '':
            return None
        if dialect.name == "postgresql":
            return value
        # SQlite convert to bytes
        if isinstance(value, bytes):
            return value
        n = ipaddress.ip_address(value)
        return _ip_network_to_bytes(n)

    def process_result_value(self, value, dialect):
        if value is None or value == '':
            return None
        if dialect.name == "postgresql":
            return value
        # SQlite convert from bytes
        return _bytes_to_ip_network(value).network_address.compressed

    class comparator_factory(String.Comparator):
        def host(self):
            return func.host(self)

        def text(self):
            return func.text(self)

        def inet(self):
            return func.inet(self)

        def family(self):
            return func.family(self)

        def broadcast(self):
            return func.broadcast(self)
