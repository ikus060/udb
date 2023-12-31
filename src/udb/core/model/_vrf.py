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

    def __str__(self):
        return self.name

    @hybrid_property
    def summary(self):
        return self.name


Index(
    'vrf_name_unique_ix',
    Vrf.name,
    unique=True,
    sqlite_where=Vrf.estatus != Vrf.STATUS_DELETED,
    postgresql_where=Vrf.estatus != Vrf.STATUS_DELETED,
    info={
        'description': _('A Vrf already exists with the same name.'),
        'field': 'name',
        'related': lambda obj: Vrf.query.filter(Vrf.estatus != Vrf.STATUS_DELETED, Vrf.name == obj.name).first(),
    },
)

Index(
    'vrf_estatus_unique_ix',
    Vrf.id,
    Vrf.estatus,
    unique=True,
)
