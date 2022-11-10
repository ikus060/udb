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

from sqlalchemy import String, TypeDecorator, event, func
from sqlalchemy.dialects.postgresql import CIDR
from sqlalchemy.engine import Engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import GenericFunction


def _sqlite_inet_broadcast(value):
    """
    Convert ip_network into comparable bytes.
    """
    if value is None:
        return None
    n = ipaddress.ip_network(value)
    return b'%s%s%s' % (
        n.version.to_bytes(2, byteorder='big'),
        n.broadcast_address.packed,
        n.prefixlen.to_bytes(2, byteorder='big'),
    )


def _sqlite_inet(value):
    """
    Convert ip_network into comparable bytes.
    """
    if value is None:
        return None
    n = ipaddress.ip_network(value)
    return b'%s%s%s' % (
        n.version.to_bytes(2, byteorder='big'),
        n.network_address.packed,
        n.prefixlen.to_bytes(2, byteorder='big'),
    )


def _sqlite_family(value):
    """
    Return the inet family.
    """
    if value is None:
        return None
    n = ipaddress.ip_network(value)
    return n.version


@event.listens_for(Engine, "connect")
def _register_sqlite_cidr_functions(dbapi_con, unused):
    """
    On SQLite engine, register custom function to support CIDR operations.
    """
    if 'sqlite' in repr(dbapi_con):
        dbapi_con.create_function("inet_broadcast", 1, _sqlite_inet_broadcast, deterministic=True)
        dbapi_con.create_function("text", 1, str, deterministic=True)
        dbapi_con.create_function("inet", 1, _sqlite_inet, deterministic=True)
        dbapi_con.create_function("family", 1, _sqlite_family, deterministic=True)


class subnet_of(GenericFunction):
    name = "subnet_of"
    inherit_cache = True


@compiles(subnet_of, "sqlite")
def _render_subnet_of_sqlite(element, compiler, **kw):
    """
    On SQLite, make use of inet() and broadcast()
    """
    left, right = element.clauses
    return "%s IS NOT NULL AND %s IS NOT NULL AND inet(%s) >= inet(%s) AND inet_broadcast(%s) < inet_broadcast(%s)" % (
        compiler.process(left, **kw),
        compiler.process(right, **kw),
        compiler.process(left, **kw),
        compiler.process(right, **kw),
        compiler.process(left, **kw),
        compiler.process(right, **kw),
    )


@compiles(subnet_of, "postgresql")
def _render_subnet_of_pg(element, compiler, **kw):
    """
    On Postgresql, register compiler to replace funcation calls by operator `<<`.
    """
    left, right = element.clauses

    return "%s %s %s" % (
        compiler.process(left, **kw),
        "<<",
        compiler.process(right, **kw),
    )


class CidrType(TypeDecorator):
    """
    Type decorator to store CIDR 192.168.0.1/24 in Postgresql database.
    In SQLite we store the value as string.
    """

    impl = CIDR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(CIDR())
        return dialect.type_descriptor(String())

    class comparator_factory(String.Comparator):
        def subnet_of(self, other):
            return func.subnet_of(self, other).as_comparison(1, 2)

        def supernet_of(self, other):
            return func.subnet_of(other, self).as_comparison(1, 2)

        def text(self):
            return func.text(self)

        def host(self):
            return func.host(self)

        def inet(self):
            return func.inet(self)

        def family(self):
            return func.family(self)
