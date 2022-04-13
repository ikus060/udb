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
from sqlalchemy import String, TypeDecorator, event, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.engine import Engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import GenericFunction
from sqlalchemy.sql.operators import match_op

"""
This module regroups all the functionnality related to provided a
ts_vector() type and function compatible with Pogresql but also a
mimic version for SQLite.
"""


def _sqlite_to_tsvector(regconfig, text):
    """
    SQLite implementation of to_tsvector() to mimic postgresql. Will Simply store the text as is.
    """
    return text


@event.listens_for(Engine, "connect")
def _register_sqlite_tsvector_functions(dbapi_con, unused):
    if 'sqlite' in repr(dbapi_con):
        dbapi_con.create_function("to_tsvector", 2, _sqlite_to_tsvector, deterministic=True)


class websearch(GenericFunction):
    name = "websearch"


@compiles(websearch, "postgresql")
def _render_websearch_of_pg(element, compiler, **kw):
    """
    On Postgresql, websearch() should use full text search functions `websearch_to_tsquery()`.
    """
    left, right = element.clauses
    return "%s @@ websearch_to_tsquery(%s)" % (
        compiler.process(left, **kw),
        compiler.process(right, **kw),
    )


@compiles(websearch, 'sqlite')
def _render_websearch_of_sqlite(element, compiler, **kw):
    """
    On SQLite, websearch uses LIKE operator.
    """
    left, right = element.clauses
    percent = compiler._like_percent_literal
    right = percent.__add__(right).__add__(percent)
    return "lower(%s) LIKE lower(%s)" % (
        compiler.process(left, **kw),
        compiler.process(right, **kw),
    )


class TSVectorType(TypeDecorator):
    """
    TSVector is a specific feature of PostgreSQL. When SQLite database is used, we simply
    store a concatenated version of all the fields and use LIKE operator to mimic the
    search. It's should be enought for demonstration.
    """

    impl = TSVECTOR
    cache_ok = True

    class comparator_factory(TSVECTOR.Comparator):
        def websearch(self, other):
            return func.websearch(self, other)

        def match(self, other):
            raise NotImplementedError('use websearch() instead')

    def __init__(self, *args, **kwargs):
        """
        Initializes new TSVectorType

        :param *args: list of column names
        :param **kwargs: various other options for this TSVectorType
        """
        self.columns = args
        self.options = kwargs
        super(TSVectorType, self).__init__()

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(TSVECTOR())
        return dialect.type_descriptor(String())

    def coerce_compared_value(self, op, value):
        if op is match_op:
            return String()
        return self
