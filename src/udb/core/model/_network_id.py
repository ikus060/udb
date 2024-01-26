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

from sqlalchemy import Integer, TypeDecorator


class NetworkId(TypeDecorator):
    """
    Type decorator to store network identifier in database in a non-nullable format by supporting undefined value (-1).
    """

    UNDEFINED = -1

    impl = Integer
    cache_ok = True
    evaluates_none = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(Integer())

    def process_bind_param(self, value, dialect):
        """
        When storing value in database, None is stored as undefined (-1).
        """
        if value is None or value == '':
            return NetworkId.UNDEFINED
        return value

    def process_result_value(self, value, dialect):
        if value == NetworkId.UNDEFINED:
            return None
        return value
