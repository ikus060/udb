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

import ipaddress
import re

import cherrypy
from sqlalchemy import CheckConstraint, Column, Computed, ForeignKey, and_, case, event, func, literal, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import aliased, declared_attr, relationship, validates
from sqlalchemy.types import Integer, String

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.tools.i18n import gettext_lazy as _

from ._cidr import InetType
from ._common import CommonMixin
from ._dnszone import DnsZone
from ._follower import FollowerMixin
from ._json import JsonMixin
from ._message import MessageMixin
from ._rule import rule
from ._search_string import SearchableMixing
from ._status import StatusMixing
from ._subnet import Subnet, SubnetRange

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


def _reverse_ipv4(value):
    """
    Validate a reverse ipv6 value used for PTR records.
    e.g.: 16.155.10.in-addr.arpa. for 10.155.16.0/22
    """
    if not value.endswith('.in-addr.arpa'):
        return None
    groups = value[0:-13].split('.')
    if len(groups) > 4:
        return None
    if any(not x.isdigit() for x in groups):
        return None
    if not all(0 <= int(part) < 256 for part in groups):
        return None
    return '.'.join([str(int(part)) for part in groups[::-1]])


def _reverse_ipv6(value):
    """
    Validate a reverse ipv6 value used for PTR records.
    e.g.: 8.b.d.0.1.0.0.2.ip6.arpa for 2001:db8::/29
    """
    if not value.endswith('.ip6.arpa'):
        return None
    groups = value[0:-9].split('.')
    if len(groups) > 32:
        return False
    valid_hex = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f']
    if not all(x in valid_hex for x in groups):
        return False
    groups = groups[::-1]
    full_address = ':'.join([''.join(groups[i : i + 4]) for i in range(0, 32, 4)])
    return str(ipaddress.ip_address(full_address))


# letters, digits, hyphen (-), underscore (_)
NAME_PATTERN = re.compile(
    r'^(?:[a-zA-Z0-9_]'  # First character of the domain
    r'(?:[a-zA-Z0-9-_]{0,61}[A-Za-z0-9_])?\.)'  # Sub domain + hostname
    r'+[a-zA-Z0-9][a-zA-Z0-9-_]{0,61}'  # First 61 characters of the gTLD
    r'[A-Za-z]$'  # Last character of the gTLD
)


def validate_domain(value):
    return NAME_PATTERN.match(value)


class DnsRecord(CommonMixin, JsonMixin, StatusMixing, MessageMixin, FollowerMixin, SearchableMixing, Base):
    _ip_column_name = 'ip_value'

    TYPES = [
        'CNAME',
        'A',
        'AAAA',
        'TXT',
        'SRV',
        'PTR',
        'CDNSKEY',
        'CDS',
        'DNSKEY',
        'DS',
        'CAA',
        'SSHFP',
        'TLSA',
        'MX',
        'NS',
        'DHCID',
        'SOA',
    ]
    name = Column(String, unique=False, nullable=False)
    type = Column(String, nullable=False)
    ttl = Column(Integer, nullable=False, default=3600)
    value = Column(String, nullable=False)

    # Relation to Ip record uses GENERATE ALWAYS
    @declared_attr
    def generated_ip(cls):
        return Column(InetType, ForeignKey("ip.ip"), Computed(cls.ip_value, persisted=True))

    @declared_attr
    def _ip(cls):
        return relationship("Ip", back_populates='related_dns_records', lazy=True)

    @classmethod
    def _search_string(cls):
        return cls.name + " " + cls.type + " " + cls.value

    def _validate(self):
        """
        Run other validation on all fields.
        """
        is_ptr = self.type == 'PTR'

        # Validate value according to record type
        if self.type not in DnsRecord.TYPES:
            raise ValueError('type', _('invalid record type'))

        # Verify domain name
        if self.type in ['CNAME', 'PTR', 'NS'] and not validate_domain(self.value):
            raise ValueError('value', _('value must be a valid domain name'))

        # Verify IP Address
        elif self.type in ['A', 'AAAA']:
            if not self.ip_value:
                raise ValueError('value', _('value must be a valid IP address'))
            self.value = self.ip_value
        elif not self.value:
            raise ValueError('value', _('value must not be empty'))

        # Every record type must be defined within a DNS Zone
        dnszone = self._get_related_dnszone()
        if not dnszone:
            raise ValueError('value' if is_ptr else 'name', _('FQDN must be defined within a valid DNS Zone.'))

        # Validate name according to record type
        if is_ptr and not self.ip_value:
            raise ValueError(
                'name',
                _('PTR records must ends with `.in-addr.arpa` or `.ip6.arpa` and define a valid IPv4 or IPv6 address'),
            )
        if self.type in ['A', 'AAAA', 'PTR']:
            # IP should be within the corresponding DNS Zone
            ip_address = ipaddress.ip_network(self.ip_value)
            all_ranges = (
                SubnetRange.query.with_entities(SubnetRange.range)
                .join(Subnet)
                .join(Subnet.dnszones)
                .filter(DnsZone.id == dnszone.id, SubnetRange.version == ip_address.version)
                .all()
            )
            combined_ranges = list(ipaddress.collapse_addresses([ipaddress.ip_network(r.range) for r in all_ranges]))
            matching_range = any(r for r in combined_ranges if r.supernet_of(ip_address))
            if not matching_range:
                suggest_subnet = ', '.join(map(str, combined_ranges))
                raise ValueError(
                    'name' if is_ptr else 'value',
                    _('IP address must be defined within the DNS Zone: %s') % suggest_subnet,
                )

    def _get_related_dnszone(self):
        """
        Return DnsZone matching our name.
        """
        return (
            DnsZone.query.filter(
                literal(self.hostname_value).endswith(DnsZone.name),
                DnsZone.status != DnsZone.STATUS_DELETED,
            )
            .order_by(func.length(DnsZone.name))
            .first()
        )

    def related_dns_record_query(self):
        """
        Return a list of DNS Record with the same `name` excluding our self.
        """
        return DnsRecord.query.filter(
            DnsRecord.hostname_value == literal(self.hostname_value),
            DnsRecord.status != DnsRecord.STATUS_DELETED,
            DnsRecord.id != self.id,
        )

    def get_reverse_dns_record(self):
        """
        For A or AAAA, return a PTR record
        For PTR record, return A or AAAA.
        Otherwise, return None
        """
        if self.type == 'PTR':
            return DnsRecord.query.filter(
                DnsRecord.type.in_(['A', 'AAAA']),
                DnsRecord.name == self.value,
                DnsRecord.value == str(self.ip_value),
                DnsRecord.status != DnsRecord.STATUS_DELETED,
            ).first()
        elif self.type in ['A', 'AAAA']:
            value = ipaddress.ip_address(self.value).reverse_pointer
            return DnsRecord.query.filter(
                DnsRecord.type == 'PTR',
                DnsRecord.name == value,
                DnsRecord.value == self.name,
                DnsRecord.status != DnsRecord.STATUS_DELETED,
            ).first()
        return None

    def create_reverse_dns_record(self, **kwargs):
        """
        For A or AAAA, return a new PTR record
        For PTR record, return new A or AAAA record.
        Otherwise, return None
        """
        if self.type == 'PTR':
            newtype = 'AAAA' if self.value.endswith('.ip6.arpa') else 'A'
            return DnsRecord(name=self.value, type=newtype, value=self.ip_value, ttl=self.ttl, **kwargs)
        elif self.type in ['A', 'AAAA']:
            value = ipaddress.ip_address(self.value).reverse_pointer
            return DnsRecord(name=value, type='PTR', value=self.name, ttl=self.ttl, **kwargs)
        return None

    @validates('name')
    def validate_name(self, key, value):
        """
        Handle special case with wildcard.
        """
        if value and value.startswith('*.'):
            if not validate_domain(value[2:]):
                raise ValueError('name', _('expected a valid FQDN'))
        elif not validate_domain(value):
            raise ValueError('name', _('expected a valid FQDN'))
        return value.lower()

    @validates('type')
    def validate_type(self, key, value):
        if value not in DnsRecord.TYPES:
            raise ValueError('type', _('expected a valid DNS record type'))
        return value

    @validates('generated_ip')
    def discard_generated_ip(self, key, value):
        """
        Discard any value that get assigned to generated column.
        """
        return self.generated_ip

    def __str__(self):
        return "%s = %s (%s)" % (self.name, self.value, self.type)

    @hybrid_property
    def summary(self):
        return self.name + " = " + self.value + " (" + self.type + ")"

    @hybrid_property
    def hostname_value(self):
        """
        Return the hostname of a DNS Record. For PTR record, this correspond to the value.
        """
        if self.type == 'PTR':
            return self.value
        return self.name

    @hostname_value.expression
    def hostname_value(cls):
        """
        Return the hostname of a DNS Record. For PTR record, this correspond to the value.
        """
        return case(
            (
                cls.type == 'PTR',
                cls.value,
            ),
            else_=cls.name,
        )

    @hybrid_property
    def ip_value(self):
        """
        Return the IP Address of a A, AAAA or PTR record.
        """
        if self.type == 'PTR':
            value = _reverse_ipv4(self.name) or _reverse_ipv6(self.name)
            if value:
                return ipaddress.ip_address(value).compressed
        elif self.type == 'A':
            try:
                return ipaddress.IPv4Address(self.value).compressed
            except ValueError:
                pass
        elif self.type == 'AAAA':
            try:
                return ipaddress.IPv6Address(self.value).compressed
            except ValueError:
                pass
        return None

    @ip_value.expression
    def ip_value(cls):
        """
        Return the IP Address of a A, AAAA or PTR record.
        """
        # Create a field to convert
        # 255.2.168.192.in-addr.arpa to 192.168.2.255
        _reverse_ipv4 = (
            func.split_part(cls.name, '.', 4)
            + '.'
            + func.split_part(cls.name, '.', 3)
            + '.'
            + func.split_part(cls.name, '.', 2)
            + '.'
            + func.split_part(cls.name, '.', 1)
        )

        def _ipv6_part(col, start):
            return func.replace(func.reverse(func.substring(col, start, 8)), '.', '')

        # Create a field to convert
        # `b.a.9.8.7.6.5.0.4.0.0.0.3.0.0.0.2.0.0.0.1.0.0.0.0.0.0.0.1.2.3.4.ip6.arpa` to
        # `4321:0000:0001:0002:0003:0004:0567:89ab`
        _reverse_ipv6 = (
            _ipv6_part(cls.name, 56)
            + ':'
            + _ipv6_part(cls.name, 48)
            + ':'
            + _ipv6_part(cls.name, 40)
            + ':'
            + _ipv6_part(cls.name, 32)
            + ':'
            + _ipv6_part(cls.name, 24)
            + ':'
            + _ipv6_part(cls.name, 16)
            + ':'
            + _ipv6_part(cls.name, 8)
            + ':'
            + _ipv6_part(cls.name, 0)
        )
        return case(
            (
                cls.type == 'A',
                func.inet(cls.value),
            ),
            (
                cls.type == 'AAAA',
                func.inet(cls.value),
            ),
            (
                and_(cls.type == 'PTR', cls.name.like('%.%.%.%.in-addr.arpa')),
                func.inet(_reverse_ipv4),
            ),
            (
                and_(
                    cls.type == 'PTR',
                    cls.name.like('%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.%.ip6.arpa'),
                ),
                func.inet(_reverse_ipv6),
            ),
            else_=None,
        )

    def objects_to_notify(self):
        """
        When getting updated, make sure to notify the DNS Zone and other DNS Record.
        """
        # Reference to our self
        objects = [(self.__tablename__, self.id)]
        # Reference to parent DNZ Zone
        try:
            dnszone = self._get_related_dnszone()
            if dnszone:
                objects.append((dnszone.__tablename__, dnszone.id))
        except Exception:
            pass
        # Reference to other DNS Record
        try:
            related = self.related_dns_record_query().all()
            objects.extend([(dnsrecord.__tablename__, dnsrecord.id) for dnsrecord in related])
        except Exception:
            pass
        return objects

    @classmethod
    def dnsrecord_sort_key(cls, record):
        """
        Return a key appropriate to be used for sorting dns records.
        """
        # Pick hostname according to record type
        hostname = record.get('name' if record.get('type', None) != 'PTR' else 'value', '')
        # Reverse order the hostname
        parts = hostname.split('.')[::-1]
        # Replace the wildcard (*) with a higher character to be sure to place the wildcard at the end of the subdomains.
        parts = [p if p != '*' else '\xff' for p in parts]

        return (
            # Make sure to place SOA records first
            record.get('type', None) != 'SOA',
            # Reverse domain name
            parts,
            # Then sort by type
            record.get('type', ''),
            # and value
            record.get('value', ''),
        )


@event.listens_for(DnsRecord, "before_update")
def before_update(mapper, connection, instance):
    instance._validate()


@event.listens_for(DnsRecord, "before_insert")
def before_insert(mapper, connection, instance):
    instance._validate()


# Make sure `type` only matches suported types.
CheckConstraint(DnsRecord.type.in_(DnsRecord.TYPES), name="dnsrecord_types")


@event.listens_for(DnsRecord.ip_value, 'set')
def dns_reload_ip(self, new_value, old_value, initiator):
    # When the ip address get updated on a record, make sure to load the relatd Ip object to update the history.
    if new_value != old_value:
        self._ip


@rule(
    DnsRecord,
    _('PTR record must have at least one corresponding forward record with the same hostname and same IP address.'),
)
def dns_ptr_without_forward():
    fwd = aliased(DnsRecord)
    return select(
        DnsRecord.id.label('id'),
        literal(DnsRecord.__tablename__).label('model_name'),
        DnsRecord.summary.label('summary'),
    ).filter(
        DnsRecord.type == 'PTR',
        DnsRecord.status == DnsRecord.STATUS_ENABLED,
        ~(
            select(fwd.id)
            .filter(
                fwd.status == DnsRecord.STATUS_ENABLED,
                fwd.type.in_(['A', 'AAAA']),
                fwd.generated_ip == DnsRecord.generated_ip,
            )
            .exists()
        ),
    )


@rule(DnsRecord, _('Alias for the canonical name (CNAME) should not be defined on a DNS Zone.'))
def dns_cname_on_dns_zone():
    """
    Return record where an alias is defined for a DNS Zone.
    """
    return (
        select(
            DnsRecord.id,
            literal(DnsRecord.__tablename__).label('model_name'),
            DnsRecord.summary.label('summary'),
            DnsZone.id.label('other_id'),
            literal(DnsZone.__tablename__).label('other_model_name'),
            DnsZone.summary.label('other_summary'),
        )
        .join(DnsZone, DnsRecord.name == DnsZone.name)
        .filter(
            DnsRecord.type == 'CNAME',
            DnsRecord.status == DnsRecord.STATUS_ENABLED,
        )
    )


@rule(DnsRecord, _('You cannot defined other record type when an alias for a canonical name (CNAME) is defined.'))
def dns_cname_not_unique():
    """
    Return all record where a CNAME is not the only record.
    """
    a = aliased(DnsRecord)
    return (
        select(
            DnsRecord.id,
            literal(DnsRecord.__tablename__).label('model_name'),
            DnsRecord.summary.label('summary'),
            a.id.label('other_id'),
            literal(DnsRecord.__tablename__).label('other_model_name'),
            a.summary.label('other_summary'),
        )
        .join(a, DnsRecord.name == a.name)
        .filter(
            or_(
                and_(DnsRecord.type == 'CNAME', a.type != 'CNAME'),
                and_(DnsRecord.type != 'CNAME', a.type == 'CNAME'),
            ),
            DnsRecord.status == DnsRecord.STATUS_ENABLED,
            a.status == DnsRecord.STATUS_ENABLED,
        )
    )
