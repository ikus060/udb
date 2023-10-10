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


class format(GenericFunction):
    name = "format"


@compiles(format, "sqlite")
def _render_format_sqlite(element, compiler, **kw):
    """
    On older SQLite format() was named `printf`
    """
    return "printf(%s)" % compiler.process(element.clauses, **kw)
