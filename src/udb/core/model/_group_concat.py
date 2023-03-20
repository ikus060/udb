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
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import GenericFunction


class group_concat(GenericFunction):
    name = "group_concat"
    inherit_cache = True

    def __init__(self, *clauses, order_by=None, **kwargs):
        self.order_by = order_by
        super().__init__(*clauses, **kwargs)


@compiles(group_concat, "postgresql")
def _render_group_concat_pg(element, compiler, **kw):
    """
    On Postgresql, `group_concat` should be `string_agg`
    """
    if element.order_by is not None:
        return "string_agg(%s, ',' ORDER BY %s)" % (
            compiler.process(element.clauses, **kw),
            compiler.process(element.order_by, **kw),
        )
    return "string_agg(%s, ',')" % (compiler.process(element.clauses, **kw),)


@compiles(group_concat, "sqlite")
def _render_group_concat_sqlite(element, compiler, **kw):
    """
    On SQLite, `group_concat` doesn't support order_by
    """
    # Ignore order_by, it's not supported by SQLite
    # Avoid defining a separator as it fail parsing when using DISTINCT
    return "group_concat(%s)" % (compiler.process(element.clauses, **kw),)
