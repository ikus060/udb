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


def _sqlite_subnet_of(value, other):
    """
    Use python function to determine the subnet.
    """
    try:
        return value != other and ipaddress.ip_network(value).subnet_of(ipaddress.ip_network(other))
    except (ValueError, TypeError):
        return False


def _sqlite_supernet_of(value, other):
    """
    Use python function to determine the subnet.
    """
    try:
        return value != other and ipaddress.ip_network(value).supernet_of(ipaddress.ip_network(other))
    except (ValueError, TypeError):
        return False


@event.listens_for(Engine, "connect")
def _register_sqlite_cidr_functions(dbapi_con, unused):
    """
    On SQLite engine, register custom function to support CIDR operations.
    """
    if 'sqlite' in repr(dbapi_con):
        dbapi_con.create_function("subnet_of", 2, _sqlite_subnet_of, deterministic=True)
        dbapi_con.create_function("supernet_of", 2, _sqlite_supernet_of, deterministic=True)
        dbapi_con.create_function("text", 1, str, deterministic=True)


class subnet_of(GenericFunction):
    name = "subnet_of"


class supernet_of(GenericFunction):
    name = "supernet_of"


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


@compiles(supernet_of, "postgresql")
def _render_supernet_of_pg(element, compiler, **kw):
    """
    On Postgresql, register compiler to replace funcation calls by operator `>>`.
    """
    left, right = element.clauses

    return "%s %s %s" % (
        compiler.process(left, **kw),
        ">>",
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
            return func.subnet_of(self, other)

        def supernet_of(self, other):
            return func.supernet_of(self, other)

        def text(self):
            return func.text(self)
