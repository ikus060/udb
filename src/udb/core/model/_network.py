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
from sqlalchemy import Column, ForeignKey, String, Table, select, event
from sqlalchemy.orm import relationship, validates, aliased
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.schema import Index
from sqlalchemy.sql.sqltypes import Integer
from udb.tools.i18n import gettext as _

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
            raise ValueError('name', _('expected a valid FQDN'))
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
            raise ValueError('ip_cidr', _(
                'expected a valid ipv4 or ipv6 address'))
        return value

    def __str__(self):
        return "%s (%s)" % (self.ip_cidr, self.name)


class DnsRecord(CommonMixin, Base):
    TYPES = {
        'CNAME': validators.domain,
        'A': validators.ipv4,
        'AAAA': validators.ipv6,
        'TXT': lambda value: value and isinstance(value, str),
        'SRV': lambda value: value and isinstance(value, str),
        'PTR': validators.domain,
        # Usable in IP address & FQDN views
        'CDNSKEY': lambda value: value and isinstance(value, str),
        'CDS': lambda value: value and isinstance(value, str),
        'DNSKEY': lambda value: value and isinstance(value, str),
        'DS': lambda value: value and isinstance(value, str),
        # Usable in DNS zones
        'CAA': lambda value: value and isinstance(value, str),
        'SSHFP': lambda value: value and isinstance(value, str),
        'TLSA': lambda value: value and isinstance(value, str),
        'MX': lambda value: value and isinstance(value, str),
        'NS': validators.domain,
    }

    name = Column(String, unique=False, nullable=False)
    type = Column(String, nullable=False)
    ttl = Column(Integer, nullable=False, default=3600)
    value = Column(String, nullable=False)

    @classmethod
    def _validate_reverse_ipv4(cls, value):
        """
        Validate a reverse ipv6 value used for PTR records.
        e.g.: 16.155.10.in-addr.arpa. for 10.155.16.0/22
        """
        groups = value.split('.')
        if len(groups) > 4:
            return False
        if any(not x.isdigit() for x in groups):
            return False
        return all(0 <= int(part) < 256 for part in groups)

    @classmethod
    def _validate_reverse_ipv6(cls, value):
        """
        Validate a reverse ipv6 value used for PTR records.
        e.g.: 8.b.d.0.1.0.0.2.ip6.arpa for 2001:db8::/29
        """
        groups = value.split('.')
        if len(groups) > 32:
            return False
        return all(x in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f'] for x in groups)

    def _validate(self):
        """
        Run other validation on all fields.
        """
        # Validate value according to record type
        validator = DnsRecord.TYPES.get(self.type)
        if not validator(self.value):
            raise ValueError('value', _(
                'value must matches the DNS record type'))

        # Validate name according to record type
        if self.type == 'PTR':
            if not(self.name.endswith('.in-addr.arpa') or self.name.endswith('.ip6.arpa')):
                raise ValueError(
                    'name', _('PTR records must ends with `.in-addr.arpa` or `.ip6.arpa`'))
            if self.name.endswith('.in-addr.arpa') and not DnsRecord._validate_reverse_ipv4(self.name[0:-13]):
                raise ValueError(
                    'name', _('PTR records must define an IPv4 address'))
            if self.name.endswith('.ip6.arpa') and not DnsRecord._validate_reverse_ipv6(self.name[0:-9]):
                raise ValueError(
                    'name', _('PTR records must define an IPv6 address'))

    @validates('name')
    def validate_name(self, key, value):
        if not validators.domain(value):
            raise ValueError('name', _('expected a valid FQDN'))
        return value

    @validates('type')
    def validate_type(self, key, value):
        if value not in DnsRecord.TYPES:
            raise ValueError('type', _('expected a valid DNS record type'))
        return value

    def __str__(self):
        return "%s = %s (%s)" % (self.name, self.value, self.type)


@event.listens_for(DnsRecord, "before_update")
def before_update(mapper, connection, instance):
    instance._validate()


@event.listens_for(DnsRecord, "before_insert")
def before_insert(mapper, connection, instance):
    instance._validate()


class DhcpRecord(CommonMixin, Base):
    ip = Column(String, nullable=False, unique=True)
    mac = Column(String, nullable=False, unique=True)

    @validates('ip')
    def validate_ip(self, key, value):
        if not validators.ipv4(value) and not validators.ipv6(value):
            raise ValueError('ip', _('expected a valid ipv4 or ipv6'))
        return value

    @validates('mac')
    def validate_mac(self, key, value):
        if not validators.mac_address(value):
            raise ValueError('mac', _('expected a valid mac'))
        return value

    def __str__(self):
        return "%s (%s)" % (self.ip, self.mac)


# Create a non-traditional mapping with multiple table.
# Read more about it here: https://docs.sqlalchemy.org/en/14/orm/nonstandard_mappings.html
ip_entry = select(DhcpRecord.ip.label('ip')).filter(DhcpRecord.status != DhcpRecord.STATUS_DELETED).union(
    select(DnsRecord.value.label('ip')).filter(DnsRecord.type.in_(['A', 'AAAA']), DnsRecord.status != DnsRecord.STATUS_DELETED)).subquery()


class Ip(Base):
    __table__ = ip_entry
    __mapper_args__ = {
        'primary_key': [ip_entry.c.ip]
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def related_dns_records(self):
        a = aliased(DnsRecord)
        return DnsRecord.query.join(a, DnsRecord.name == a.name).filter(a.value == self.ip).all()

    @property
    def related_dhcp_records(self):
        return DhcpRecord.query.filter(DhcpRecord.ip == self.ip).all()
