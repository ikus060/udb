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
from sqlalchemy import String, TypeDecorator, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import GenericFunction
from sqlalchemy.sql.operators import match_op

"""
This module regroups all the functionnality related to provided a
ts_vector() type and function compatible with Pogresql but also a
mimic version for SQLite.
"""


class to_tsvector(GenericFunction):
    name = "to_tsvector"
    inherit_cache = True


@compiles(to_tsvector, "postgresql")
def _render_to_tsvector_of_pg(element, compiler, **kw):
    """
    On Postgresql, websearch() uses ts_vector, but we need to replace dot to create multiple "word" out of foo.bar.example.com
    """
    return "to_tsvector('simple', replace(%s, '.', ' '))" % compiler.process(element.clauses, **kw)


@compiles(to_tsvector, 'sqlite')
def _render_to_tsvector_of_sqlite(element, compiler, **kw):
    """
    On SQLite, websearch uses LIKE operator, so simply lowercase the text value.
    """
    return "lower(%s)" % compiler.process(element.clauses, **kw)


class websearch(GenericFunction):
    name = "websearch"
    inherit_cache = False
    # True to look in database with wildcard instead of exact matches
    typeahead = False

    def __init__(self, *args, **kwargs):
        self.typeahead = kwargs.pop('typeahead', False)
        super().__init__(*args, **kwargs)


@compiles(websearch, "postgresql")
def _render_websearch_of_pg(element, compiler, **kw):
    """
    On Postgresql, websearch() should use full text search functions `websearch_to_tsquery()`.
    """
    left, right = element.clauses
    if element.typeahead:
        # Append wildcard lookup for last word only.
        return "%s @@ to_tsquery('simple', websearch_to_tsquery('simple', replace(%s, '.', ' '))::text || ':*')" % (
            compiler.process(left, **kw),
            compiler.process(right, **kw),
        )
    return "%s @@ websearch_to_tsquery('simple', replace(%s, '.', ' '))" % (
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
    return "%s LIKE lower(%s)" % (
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
        def websearch(self, other, **kwargs):
            return func.websearch(self, other, **kwargs)

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
