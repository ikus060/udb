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
from sqlalchemy import Column, Index
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import validates
from sqlalchemy.types import String

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.tools.i18n import gettext_lazy as _

from ._common import CommonMixin
from ._follower import FollowerMixin
from ._json import JsonMixin
from ._message import MessageMixin
from ._search_string import SearchableMixing
from ._status import StatusMixing

Base = cherrypy.tools.db.get_base()


class Vrf(CommonMixin, JsonMixin, StatusMixing, MessageMixin, FollowerMixin, SearchableMixing, Base):
    name = Column(String, nullable=False)

    @classmethod
    def _search_string(cls):
        return cls.name + " " + cls.notes

    @validates('name')
    def _validate_name(self, key, value):
        value = value.strip()
        if not value:
            raise ValueError('name', _('VRF name cannot be empty.'))
        return value

    def __str__(self):
        return self.name

    @hybrid_property
    def summary(self):
        return self.name


Index(
    'vrf_name_key',
    Vrf.name,
    unique=True,
    sqlite_where=Vrf.status == Vrf.STATUS_ENABLED,
    postgresql_where=Vrf.status == Vrf.STATUS_ENABLED,
    info={
        'description': _('A Vrf aready exist with the same name.'),
        'field': 'name',
        'other': lambda ctx: Vrf.query.filter(Vrf.status == Vrf.STATUS_ENABLED, Vrf.name == ctx['name']).first()
        if 'name' in ctx
        else None,
    },
)
