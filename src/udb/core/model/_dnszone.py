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

import re

import cherrypy
from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Table, event, func
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.types import String

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.tools.i18n import gettext_lazy as _

from ._common import CommonMixin
from ._follower import FollowerMixin
from ._json import JsonMixin
from ._message import MessageMixin
from ._search_string import SearchableMixing
from ._status import StatusMixing
from ._subnet import Subnet

# letters, digits, hyphen (-), underscore (_)
NAME_PATTERN = re.compile(
    r'^(?:[a-zA-Z0-9_]'  # First character of the domain
    r'(?:[a-zA-Z0-9\-_]{0,61}[A-Za-z0-9_])?\.)'  # Sub domain + hostname
    r'+[a-zA-Z0-9][a-zA-Z0-9\-_]{0,61}'  # First 61 characters of the gTLD
    r'[A-Za-z]$'  # Last character of the gTLD
)


Base = cherrypy.tools.db.get_base()

dnszone_subnet = Table(
    'dnszone_subnet',
    Base.metadata,
    Column('dnszone_id', ForeignKey('dnszone.id'), primary_key=True),
    Column('subnet_id', ForeignKey('subnet.id'), primary_key=True),
)


class DnsZone(CommonMixin, JsonMixin, StatusMixing, MessageMixin, FollowerMixin, SearchableMixing, Base):
    name = Column(String, nullable=False)
    subnets = relationship(
        "Subnet",
        secondary=dnszone_subnet,
        secondaryjoin=(Subnet.id == dnszone_subnet.c.subnet_id),
        backref="dnszones",
        active_history=True,
        sync_backref=True,
        lazy=True,
    )

    @classmethod
    def _search_string(cls):
        return cls.name + " " + cls.notes

    def __str__(self):
        return self.name

    @hybrid_property
    def summary(self):
        return self.name


# Make DNS Zone name (FQDN) unique without case-sensitive
Index(
    'dnszone_name_unique_ix',
    DnsZone.name,
    unique=True,
    sqlite_where=DnsZone.estatus != DnsZone.STATUS_DELETED,
    postgresql_where=DnsZone.estatus != DnsZone.STATUS_DELETED,
    info={
        'description': _('A DNS Zone aready exist for this domain.'),
        'field': 'name',
        'related': lambda obj: DnsZone.query.filter(
            DnsZone.estatus != DnsZone.STATUS_DELETED, DnsZone.name == obj.name
        ).first(),
    },
)

Index(
    'dnszone_id_name_estatus_unique_ix',
    DnsZone.id,
    DnsZone.name,
    DnsZone.estatus,
    unique=True,
)


CheckConstraint(
    DnsZone.name.regexp_match(NAME_PATTERN.pattern),
    name="dnszone_domain_name",
    info={
        'description': _('must be a valid domain name'),
        'field': 'name',
    },
)

CheckConstraint(
    DnsZone.name == func.lower(DnsZone.name),
    name="dnszone_lower_case_name",
    info={
        'description': _('Enter domain with lower case.'),
        'field': 'name',
    },
)


@event.listens_for(Base.metadata, 'after_create')
def create_arpa_zone(target, conn, **kw):
    # To allow usage of ORM session within DDL scope, we need to manually assign the connection to our current session.
    DnsZone.session.bind = conn

    # Create default reverse pointer zone.
    for name in ['in-addr.arpa', 'ip6.arpa']:
        zone = DnsZone.query.filter(DnsZone.name == name).first()
        if not zone:
            DnsZone(name=name).add().flush()
