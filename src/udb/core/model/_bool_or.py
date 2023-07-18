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


class bool_or(GenericFunction):
    name = "bool_or"
    inherit_cache = True


@compiles(bool_or, "sqlite")
def _render_bool_or_sqlite(element, compiler, **kw):
    """
    On SQLite, `bool_or` is not suported, so we use sum()
    """
    return "CASE WHEN max(%s) > 0 THEN 1 ELSE 0 END" % (compiler.process(element.clauses, **kw),)
