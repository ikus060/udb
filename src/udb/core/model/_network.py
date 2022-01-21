# -*- coding: utf-8 -*-
# udb, A web interface to manage IT network
# Copyright (C) 2021 IKUS Software inc.
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
from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.schema import Index
from sqlalchemy.sql.sqltypes import Integer

from ._common import CommonMixin

Base = cherrypy.tools.db.get_base()

dnszone_subnet = Table(
    'dnszone_subnet', Base.metadata,
    Column('dnszone_id', ForeignKey('dnszone.id')),
    Column('subnet_id', ForeignKey('subnet.id'))
)


class DnsZone(CommonMixin, Base):
    name = Column(String, unique=True, nullable=False)
    subnets = relationship("Subnet",
                           secondary=dnszone_subnet,
                           backref="dnszones",
                           active_history=True,
                           sync_backref=True)

    @validates('name')
    def validate_name(self, key, value):
        if not validators.domain(value):
            raise ValueError(value)
        return value

    def __str__(self):
        return self.name


# Make DNS Zone name (FQDN) unique without case-sensitive
Index('dnszone_name_index', func.lower(DnsZone.name), unique=True)


class Subnet(CommonMixin, Base):
    name = Column(String, unique=True, nullable=False, default='')
    ip_cidr = Column(String, unique=True, nullable=False)
    vrf = Column(Integer, nullable=True)

    @validates('ip_cidr')
    def validate_name(self, key, value):
        if not validators.ipv4_cidr(value) and not validators.ipv6_cidr(value):
            raise ValueError(value)
        return value

    def __str__(self):
        return "%s (%s)" % (self.ip_cidr, self.name)


class DnsRecord(CommonMixin, Base):
    TYPES = ['CNAME', 'A', 'AAAA', 'TXT']

    name = Column(String, unique=False, nullable=False)
    type = Column(String, nullable=False)
    ttl = Column(Integer, nullable=False, default=3600)
    value = Column(String, nullable=False)

    @validates('name')
    def validate_name(self, key, value):
        if not validators.domain(value):
            raise ValueError(value)
        return value

    @validates('type')
    def validate_type(self, key, value):
        if value not in DnsRecord.TYPES:
            raise ValueError(value)
        return value

    @validates('value')
    def validate_value(self, key, value):
        valid = True
        if self.type == 'A':
            # A Record should be a valid IP address
            valid = validators.ipv4(value)
        if self.type == 'AAAA':
            # AAAA Record should be a valid IPv6 address
            valid = validators.ipv6(value)
        elif self.type == 'CNAME':
            # CNAME should be a valid FQDN
            valid = validators.domain(value)
        elif self.type == 'TXT':
            # TXT may contain any value
            valid = value and isinstance(value, str)
        if not valid:
            raise ValueError(value)
        return value


class DhcpRecord(CommonMixin, Base):
    ip = Column(String, nullable=False, unique=True)
    mac = Column(String, nullable=False, unique=True)

    @validates('ip')
    def validate_ip(self, key, value):
        if not validators.ipv4(value) and not validators.ipv6(value):
            raise ValueError(value)
        return value

    @validates('mac')
    def validate_mac(self, key, value):
        if not validators.mac_address(value):
            raise ValueError(value)
        return value
