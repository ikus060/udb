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

from sqlalchemy import Column, Computed, String, event, func
from sqlalchemy.engine import Engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import declared_attr, deferred
from sqlalchemy.sql.functions import GenericFunction


@event.listens_for(Engine, "connect")
def _register_pg_trgm(dbapi_con, unused):
    """
    On PostgreSQL engine, make sure pg_trgm extension is installed to create index on search_string.
    """
    if 'psycopg' in repr(dbapi_con.__class__):
        with dbapi_con.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


class udb_websearch(GenericFunction):
    """
    Custom search function to make use of trgm index.
    """

    name = "udb_websearch"
    inherit_cache = False
    # True to look in database with wildcard instead of exact matches
    typeahead = False

    def __init__(self, *args, **kwargs):
        self.typeahead = kwargs.pop('typeahead', False)
        super().__init__(*args, **kwargs)


@compiles(udb_websearch, "postgresql")
def _render_udb_websearch_of_pg(element, compiler, **kw):
    """
    On Postgresql, udb_websearch() uses LIKE Operator.
    """
    left, right = element.clauses
    percent = compiler._like_percent_literal
    right = func.all(
        func.string_to_array(
            percent.__add__(func.regexp_replace(func.lower(right), '[^\\w]+', '% %', 'gi')).__add__(percent), ' '
        )
    )
    return "%s LIKE %s" % (
        compiler.process(left, **kw),
        compiler.process(right, **kw),
    )


@compiles(udb_websearch, 'sqlite')
def _render_udb_websearch_of_sqlite(element, compiler, **kw):
    """
    On SQLite, udb_websearch uses LIKE operator.
    """
    left, right = element.clauses
    percent = compiler._like_percent_literal
    right = percent.__add__(func.lower(right)).__add__(percent)
    return "%s LIKE %s" % (
        compiler.process(left, **kw),
        compiler.process(right, **kw),
    )


class SearchableMixing(object):
    """
    Searchable mixin to support tsvector.
    """

    @declared_attr
    def search_string(cls):
        """
        Create a column with text search for fast lookup.
        """
        return deferred(
            Column(
                String,
                Computed(
                    func.lower(cls._search_string()),
                    persisted=True,
                ),
            )
        )

    @classmethod
    def _search_string(cls):
        raise NotImplementedError()


# TODO Will need to create GIN trigram index on search_string
# CREATE INDEX search_string_trgm_idx ON changeme USING GIN (search_string gin_trgm_ops);
# https://www.postgresql.org/docs/9.5/pgtrgm.html

# TODO Make REGEXP_REPLACE working in SQLite ?
# Obviously index wont work.
