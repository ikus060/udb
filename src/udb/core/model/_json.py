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


class JsonMixin:
    def to_json(self):
        def _value(value):
            if hasattr(value, 'isoformat'):  # datetime
                return value.isoformat()
            return value

        return {c.name: _value(getattr(self, c.name)) for c in self.__table__.columns if not c.name.startswith('_')}

    def from_json(self, data):
        for k, v in data.items():
            setattr(self, k, v)