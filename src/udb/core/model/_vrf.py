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


import cherrypy
from sqlalchemy import Column
from sqlalchemy.orm import validates
from sqlalchemy.types import String

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.tools.i18n import gettext_lazy as _

from ._common import CommonMixin

Base = cherrypy.tools.db.get_base()


class Vrf(CommonMixin, Base):
    name = Column(String, unique=True, nullable=False)

    @validates('ip_cidr')
    def _validate_name(self, key, value):
        value = value.strip()
        if not value:
            raise ValueError('name', _('VRF name cannot be empty.'))
        return value

    def __str__(self):
        return self.name
