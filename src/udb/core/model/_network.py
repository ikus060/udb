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

import ipaddress

import cherrypy
import validators
from sqlalchemy import Column, ForeignKey, Index, Table, event, func, literal, or_, select, union
from sqlalchemy.engine import Engine
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, validates
from sqlalchemy.types import Integer, String

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.tools.i18n import gettext_lazy as _

from ._cidr import CidrType
from ._common import CommonMixin

Base = cherrypy.tools.db.get_base()


def _sqlite_split_part(string, delimiter, position):
    """
    SQLite implementation of split_part.
    https://www.postgresqltutorial.com/postgresql-split_part/
    """
    assert delimiter
    assert position >= 1
    parts = string.split(delimiter)
    if len(parts) >= position:
        return parts[position - 1]
    return None


def _sqlite_reverse(string):
    """
    SQLite implementation of reverse.
    """
    return string[::-1]


@event.listens_for(Engine, "connect")
def _register_sqlite_functions(dbapi_con, unused):
    if 'sqlite' in repr(dbapi_con):
        dbapi_con.create_function("split_part", 3, _sqlite_split_part, deterministic=True)
        dbapi_con.create_function("reverse", 1, _sqlite_reverse, deterministic=True)


dnszone_subnet = Table(
    'dnszone_subnet',
    Base.metadata,
    Column('dnszone_id', ForeignKey('dnszone.id')),
    Column('subnet_id', ForeignKey('subnet.id')),
)


class DnsZone(CommonMixin, Base):
    display_name = _('DNS Zone')
    name = Column(String, unique=True, nullable=False)
    subnets = relationship(
        "Subnet", secondary=dnszone_subnet, backref="dnszones", active_history=True, sync_backref=True
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


class Subnet(CommonMixin, Base):
    display_name = _('IP Subnet')
    name = Column(String, unique=True, nullable=False, default='')
    # Database are not very friendly when it come to storing 128bits for this reason, we are storing the network address as bit into a string field.
    ip_cidr = Column(CidrType, unique=True, nullable=False)
    vrf = Column(Integer, nullable=True)

    @classmethod
    def _search_string(cls):
        return cls.name + " " + cls.notes + " " + cls.ip_cidr.text()

    @validates('ip_cidr')
    def validate_ip(self, key, value):
        try:
            return str(ipaddress.ip_network(value, strict=False))
        except ValueError as e:
            raise ValueError('ip_cidr', str(e))

    @property
    def related_supernets(self):
        return Subnet.query.filter(Subnet.ip_cidr.supernet_of(self.ip_cidr)).all()

    @property
    def related_subnets(self):
        return Subnet.query.filter(Subnet.ip_cidr.subnet_of(self.ip_cidr)).all()

    def __str__(self):
        return "%s (%s)" % (self.ip_cidr, self.name)

    @hybrid_property
    def summary(self):
        return self.ip_cidr + " (" + self.name + ")"


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
    display_name = _('DNS Record')
    name = Column(String, unique=False, nullable=False)
    type = Column(String, nullable=False)
    ttl = Column(Integer, nullable=False, default=3600)
    value = Column(String, nullable=False)

    @classmethod
    def _search_string(cls):
        return cls.name + " " + cls.type + " " + cls.value

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
        return all(
            x in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f'] for x in groups
        )

    def _validate(self):
        """
        Run other validation on all fields.
        """
        # Validate value according to record type
        validator = DnsRecord.TYPES.get(self.type)
        if not validator(self.value):
            raise ValueError('value', _('value must matches the DNS record type'))

        if self.type == 'PTR':
            # Validate name according to record type
            if not (self.name.endswith('.in-addr.arpa') or self.name.endswith('.ip6.arpa')):
                raise ValueError('name', _('PTR records must ends with `.in-addr.arpa` or `.ip6.arpa`'))
            if self.name.endswith('.in-addr.arpa') and not DnsRecord._validate_reverse_ipv4(self.name[0:-13]):
                raise ValueError('name', _('PTR records must define an IPv4 address'))
            if self.name.endswith('.ip6.arpa') and not DnsRecord._validate_reverse_ipv6(self.name[0:-9]):
                raise ValueError('name', _('PTR records must define an IPv6 address'))
        else:
            # Every other record type must be defined within a DNS Zone
            dnszones = self.related_dnszones
            if not dnszones:
                raise ValueError('name', _('FQDN must be defined within a valid DNS Zone.'))

            # Validate IP according
            if self.type in ['A', 'AAAA'] and not self.related_subnets:
                suggest_subnet = ', '.join([', '.join(map(lambda x: x.ip_cidr, zone.subnets)) for zone in dnszones])
                raise ValueError('value', _('IP address must be defined within the DNS Zone: %s') % suggest_subnet)

    @property
    def related_dnszones(self):
        """
        Return list of DnsZone matching our name.
        """
        return DnsZone.query.filter(
            literal(self.name).endswith(DnsZone.name),
            DnsZone.status != DnsZone.STATUS_DELETED,
        ).all()

    @property
    def related_subnets(self):
        """
        Return list of subnet matching our dnszone (name) and ip address (value).
        """
        if self.type not in ['A', 'AAAA']:
            return []
        return (
            Subnet.query.join(Subnet.dnszones)
            .filter(
                literal(self.name).endswith(DnsZone.name),
                Subnet.ip_cidr.supernet_of(self.value),
                DnsZone.status != DnsZone.STATUS_DELETED,
                Subnet.status != Subnet.STATUS_DELETED,
            )
            .all()
        )

    @validates('name')
    def validate_name(self, key, value):
        if not validators.domain(value):
            raise ValueError('name', _('expected a valid FQDN'))
        return value.lower()

    @validates('type')
    def validate_type(self, key, value):
        if value not in DnsRecord.TYPES:
            raise ValueError('type', _('expected a valid DNS record type'))
        return value

    def __str__(self):
        return "%s = %s (%s)" % (self.name, self.value, self.type)

    @hybrid_property
    def summary(self):
        return self.name + " = " + self.value + "(" + self.type + ")"


@event.listens_for(DnsRecord, "before_update")
def before_update(mapper, connection, instance):
    instance._validate()


@event.listens_for(DnsRecord, "before_insert")
def before_insert(mapper, connection, instance):
    instance._validate()


class DhcpRecord(CommonMixin, Base):
    display_name = _('DHCP Record')
    ip = Column(String, nullable=False, unique=True)
    mac = Column(String, nullable=False, unique=True)

    @classmethod
    def _search_string(cls):
        return cls.ip + " " + cls.mac + " " + cls.notes

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

    @hybrid_property
    def summary(self):
        return self.ip + " (" + self.mac + ")"


# Create a non-traditional mapping with multiple table.
# Read more about it here: https://docs.sqlalchemy.org/en/14/orm/nonstandard_mappings.html
def _ipv6_part(col, start):
    return func.ltrim(func.replace(func.reverse(func.substring(col, start, 8)), '.', ''), '0')


# Create a field to convert
# 255.2.168.192.in-addr.arpa
# to
# 192.168.2.255
_reverse_ptr_ipv4 = (
    func.split_part(DnsRecord.name, '.', 4)
    + '.'
    + func.split_part(DnsRecord.name, '.', 3)
    + '.'
    + func.split_part(DnsRecord.name, '.', 2)
    + '.'
    + func.split_part(DnsRecord.name, '.', 1)
)

# Create a field to convert
# `b.a.9.8.7.6.5.0.4.0.0.0.3.0.0.0.2.0.0.0.1.0.0.0.0.0.0.0.1.2.3.4.ip6.arpa` to
# `4321:0:1:2:3:4:567:89ab`
_reverse_ptr_ipv6 = (
    _ipv6_part(DnsRecord.name, 56)
    + ':'
    + _ipv6_part(DnsRecord.name, 48)
    + ':'
    + _ipv6_part(DnsRecord.name, 40)
    + ':'
    + _ipv6_part(DnsRecord.name, 32)
    + ':'
    + _ipv6_part(DnsRecord.name, 24)
    + ':'
    + _ipv6_part(DnsRecord.name, 16)
    + ':'
    + _ipv6_part(DnsRecord.name, 8)
    + ':'
    + _ipv6_part(DnsRecord.name, 0)
)

# Create a query to list all existing IP address in various record type.
ip_entry = union(
    select(DhcpRecord.ip.label('ip')).filter(DhcpRecord.status != DhcpRecord.STATUS_DELETED),
    select(DnsRecord.value.label('ip')).filter(
        DnsRecord.type.in_(['A', 'AAAA']), DnsRecord.status != DnsRecord.STATUS_DELETED
    ),
    select(_reverse_ptr_ipv4.label('ip')).filter(
        DnsRecord.type == 'PTR',
        DnsRecord.status != DnsRecord.STATUS_DELETED,
        DnsRecord.name.like('%.%.%.%.in-addr.arpa'),
    ),
    select(_reverse_ptr_ipv6.label('ip')).filter(
        DnsRecord.type == 'PTR',
        DnsRecord.status != DnsRecord.STATUS_DELETED,
        DnsRecord.name.like('%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.ip6.arpa'),
    ),
).subquery()


class Ip(Base):
    """
    This ORM is a view on all IP address declared in various record type.
    """

    display_name = _('IP Address')
    __table__ = ip_entry
    __mapper_args__ = {'primary_key': [ip_entry.c.ip]}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def related_dns_records(self):
        """
        Return list of related DNS record. That include all DNS record with FQDN matching our current IP address and reverse pointer (PTR).
        """
        return DnsRecord.query.filter(
            or_(
                DnsRecord.name.in_(select(DnsRecord.name).filter(DnsRecord.value == self.ip)),
                DnsRecord.name == ipaddress.ip_address(self.ip).reverse_pointer,
            )
        ).all()

    @property
    def related_dhcp_records(self):
        return DhcpRecord.query.filter(DhcpRecord.ip == self.ip).all()
