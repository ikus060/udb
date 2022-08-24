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
import validators
from sqlalchemy import Column, ForeignKey, Index, Table, and_, func, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import column_property, relationship, validates
from sqlalchemy.types import String

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.tools.i18n import gettext_lazy as _

from ._common import CommonMixin
from ._subnet import Subnet

Base = cherrypy.tools.db.get_base()

dnszone_subnet = Table(
    'dnszone_subnet',
    Base.metadata,
    Column('dnszone_id', ForeignKey('dnszone.id')),
    Column('subnet_id', ForeignKey('subnet.id')),
)


class DnsZone(CommonMixin, Base):
    name = Column(String, unique=True, nullable=False)
    subnets = relationship(
        "Subnet",
        secondary=dnszone_subnet,
        secondaryjoin=lambda: and_(Subnet.id == dnszone_subnet.c.subnet_id, Subnet.status != Subnet.STATUS_DELETED),
        backref="dnszones",
        active_history=True,
        sync_backref=True,
    )

    @classmethod
    def __declare_last__(cls):
        cls.subnets_count = column_property(
            select(func.count(Subnet.id))
            .where(
                and_(
                    Subnet.id == dnszone_subnet.c.subnet_id,
                    Subnet.status != Subnet.STATUS_DELETED,
                    dnszone_subnet.c.dnszone_id == DnsZone.id,
                )
            )
            .scalar_subquery(),
            deferred=True,
        )

    @classmethod
    def _search_string(cls):
        return cls.name + " " + cls.notes

    @validates('name')
    def validate_name(self, key, value):
        if not validators.domain(value):
            raise ValueError('name', _('expected a valid FQDN'))
        return value

    def __str__(self):
        return self.name

    @hybrid_property
    def summary(self):
        return self.name


# Make DNS Zone name (FQDN) unique without case-sensitive
Index('dnszone_name_index', func.lower(DnsZone.name), unique=True)
