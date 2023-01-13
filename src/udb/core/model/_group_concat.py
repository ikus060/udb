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


@compiles(group_concat, "postgresql")
def _render_group_concat_pg(element, compiler, **kw):
    """
    On Postgresql, `group_concat` should be `string_agg`
    """
    return "string_agg(%s, ',')" % (compiler.process(element.clauses, **kw),)
