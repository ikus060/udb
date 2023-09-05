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
from collections import namedtuple

import cherrypy
from sqlalchemy import (
    CheckConstraint,
    Column,
    Computed,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    and_,
    case,
    event,
    func,
    literal,
    or_,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import aliased, declared_attr, relationship, validates
from sqlalchemy.types import Integer, String

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.tools.i18n import gettext_lazy as _

from ._cidr import InetType
from ._common import CommonMixin
from ._dnszone import NAME_PATTERN, DnsZone
from ._follower import FollowerMixin
from ._json import JsonMixin
from ._message import MessageMixin
from ._rule import Rule, RuleConstraint
from ._search_string import SearchableMixing
from ._status import StatusMixing
from ._subnet import Subnet, SubnetRange
from ._vrf import Vrf

Base = cherrypy.tools.db.get_base()


def _collapse_subnet_ranges(obj):
    """
    Collapse the list of subnet range return by the query.
    """
    if not obj:
        return obj
    # Get list of range
    ranges = obj.summary.split(',')
    # Convert string to ip_network objects
    ranges = [ipaddress.ip_network(r) for r in ranges]
    # Combine the range
    combined_ranges = sorted(list(ipaddress.collapse_addresses(ranges)))
    # Replace original summary by our combined range
    new_obj = namedtuple('Row', ['model_id', 'model_name', 'summary'])
    return new_obj(
        obj.model_id,
        obj.model_name,
        ', '.join(map(str, combined_ranges)),
    )


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
    vrf_id = Column(Integer, ForeignKey("vrf.id"), nullable=True)
    vrf = relationship(Vrf)
    __table_args__ = (ForeignKeyConstraint(["generated_ip", "vrf_id"], ["ip.ip", "ip.vrf_id"]),)

    # Relation to Ip record uses GENERATE ALWAYS
    @declared_attr
    def generated_ip(cls):
        return Column(InetType, Computed(cls.ip_value, persisted=True))

    @declared_attr
    def _ip(cls):
        return relationship(
            "Ip",
            back_populates='related_dns_records',
            lazy=True,
            foreign_keys="[DnsRecord.generated_ip]",
        )

    @classmethod
    def _search_string(cls):
        return cls.name + " " + cls.type + " " + cls.value

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
            return DnsRecord(name=self.value, type=newtype, value=self.ip_value, ttl=self.ttl, vrf=self.vrf, **kwargs)
        elif self.type in ['A', 'AAAA']:
            value = ipaddress.ip_address(self.value).reverse_pointer
            return DnsRecord(name=value, type='PTR', value=self.name, ttl=self.ttl, vrf=self.vrf, **kwargs)
        return None

    @validates('name')
    def validate_name(self, key, value):
        # Make all name lower case
        return value.lower()

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

    def _validate(self):
        # This is the only application level validation to be done to avoid raising an exception calling Postgresql.::inet() function.
        if self.type == 'A' and self.ip_value is None:
            raise ValueError('value', _('value must be a valid IPv4 address'))
        elif self.type == 'AAAA' and self.ip_value is None:
            raise ValueError('value', _('value must be a valid IPv6 address'))
        elif self.type == 'PTR' and self.ip_value is None:
            raise ValueError(
                'name',
                _('PTR records must ends with `.in-addr.arpa` or `.ip6.arpa` and define a valid IPv4 or IPv6 address'),
            )

    def find_vrf(self):
        """
        Lookup database to find the best matching VRF for this record.
        """
        q = (
            Vrf.query.join(Subnet.vrf)
            .join(Subnet.subnet_ranges)
            .join(Subnet.dnszones)
            .filter(
                literal(self.name).endswith(DnsZone.name),
                SubnetRange.version == func.family(literal(self.ip_value)),
                SubnetRange.start_ip <= func.inet(literal(self.ip_value)),
                SubnetRange.end_ip >= func.inet(literal(self.ip_value)),
                DnsZone.status == DnsZone.STATUS_ENABLED,
                Subnet.status == Subnet.STATUS_ENABLED,
            )
        )
        return q.all()


@event.listens_for(DnsRecord, "before_update")
def before_update(mapper, connection, instance):
    instance._validate()


@event.listens_for(DnsRecord, "before_insert")
def before_insert(mapper, connection, instance):
    instance._validate()


@event.listens_for(DnsRecord.ip_value, 'set')
def dns_reload_ip(self, new_value, old_value, initiator):
    # When the ip address get updated on a record, make sure to load the relatd Ip object to update the history.
    if new_value != old_value:
        self._ip


# Make sure `type` only matches suported types.
CheckConstraint(DnsRecord.type.in_(DnsRecord.TYPES), name="dnsrecord_types")

dnsrecord_value_not_empty = CheckConstraint(
    DnsRecord.value != '',
    name="dnsrecord_value_not_empty",
    info={
        'description': _('value must not be empty'),
        'field': 'value',
    },
)

# When type is CNAME, PTR or NS, value must be a valid domain name.
dnsrecord_value_domain_name = CheckConstraint(
    or_(DnsRecord.type.not_in(['CNAME', 'NS', 'PTR']), DnsRecord.value.regexp_match(NAME_PATTERN.pattern)),
    name="dnsrecord_value_domain_name",
    info={
        'description': _('value must be a valid domain name'),
        'field': 'value',
    },
)

# When type is A, AAAA value must be a valid IP.
dnsrecord_a_invalid_ip = CheckConstraint(
    or_(DnsRecord.type != 'A', and_(DnsRecord.generated_ip.is_not(None), func.family(DnsRecord.generated_ip) == 4)),
    name="dnsrecord_a_invalid_ip_value",
    info={
        'description': _('value must be a valid IPv4 address'),
        'field': 'value',
    },
)

dnsrecord_aaaa_invalid_ip = CheckConstraint(
    or_(DnsRecord.type != 'AAAA', and_(DnsRecord.generated_ip.is_not(None), func.family(DnsRecord.generated_ip) == 6)),
    name="dnsrecord_aaaa_invalid_ip_value",
    info={
        'description': _('value must be a valid IPv6 address'),
        'field': 'value',
    },
)

dnsrecord_ptr_invalid_ip = CheckConstraint(
    or_(
        DnsRecord.type != 'PTR',
        and_(
            DnsRecord.name.endswith('.in-addr.arpa'),
            and_(DnsRecord.generated_ip.is_not(None), func.family(DnsRecord.generated_ip) == 4),
        ),
        and_(
            DnsRecord.name.endswith('.ip6.arpa'),
            and_(DnsRecord.generated_ip.is_not(None), func.family(DnsRecord.generated_ip) == 6),
        ),
    ),
    name="dnsrecord_ptr_invalid_ip",
    info={
        'description': _(
            'PTR records must ends with `.in-addr.arpa` or `.ip6.arpa` and define a valid IPv4 or IPv6 address'
        ),
        'field': 'name',
    },
)

dnsrecord_a_aaaa_ptr_without_vrf = CheckConstraint(
    or_(
        DnsRecord.vrf_id.is_not(None),
        DnsRecord.type.not_in(['A', 'AAAA', 'PTR']),
    ),
    name="dnsrecord_a_aaaa_ptr_without_vrf",
    info={
        'description': _('A VRF is required for this type of DNS Record.'),
        'field': 'vrf_id',
    },
)

# Make sure only one SOA record exists.
Index(
    'dnsrecord_soa_uniq_index',
    DnsRecord.name,
    unique=True,
    sqlite_where=and_(DnsRecord.type == 'SOA', DnsRecord.status == DnsRecord.STATUS_ENABLED),
    postgresql_where=and_(DnsRecord.type == 'SOA', DnsRecord.status == DnsRecord.STATUS_ENABLED),
    info={
        'description': _('An SOA record already exist for this domain.'),
        'field': 'name',
        'related': lambda obj: DnsRecord.query.filter(
            DnsRecord.type == 'SOA', DnsRecord.status == DnsRecord.STATUS_ENABLED, DnsRecord.name == obj.name
        ).first(),
    },
)

RuleConstraint(
    name='dns_without_dns_zone',
    model=DnsRecord,
    severity=Rule.SEVERITY_ENFORCED,
    statement=select(DnsRecord.id.label('id'), DnsRecord.summary.label('name')).filter(
        # SOA and PTR are validated with another rule.
        DnsRecord.type.in_([t for t in DnsRecord.TYPES if t not in ['SOA', 'PTR']]),
        DnsRecord.status == DnsRecord.STATUS_ENABLED,
        ~(
            select(DnsZone.id)
            .filter(
                DnsZone.status == DnsZone.STATUS_ENABLED,
                DnsRecord.name.endswith(DnsZone.name),
            )
            .exists()
        ),
    ),
    info={
        'description': _('Hostname must be defined within a valid DNS Zone.'),
        'field': 'name',
    },
)

RuleConstraint(
    name='dns_ptr_without_dns_zone',
    model=DnsRecord,
    severity=Rule.SEVERITY_ENFORCED,
    statement=select(DnsRecord.id.label('id'), DnsRecord.summary.label('name')).filter(
        # SOA and PTR are validated with another rule.
        DnsRecord.type == 'PTR',
        DnsRecord.status == DnsRecord.STATUS_ENABLED,
        ~(
            select(DnsZone.id)
            .filter(
                DnsZone.status == DnsZone.STATUS_ENABLED,
                DnsRecord.value.endswith(DnsZone.name),
            )
            .exists()
        ),
    ),
    info={
        'description': _('Hostname must be defined within a valid DNS Zone.'),
        'field': 'value',
    },
)

RuleConstraint(
    name="dns_ptr_without_forward",
    model=DnsRecord,
    statement=(
        lambda: (fwd := aliased(DnsRecord))
        and select(DnsRecord.id.label('id'), DnsRecord.summary.label('name'),).filter(
            DnsRecord.type == 'PTR',
            DnsRecord.status == DnsRecord.STATUS_ENABLED,
            ~(
                select(fwd.id)
                .filter(
                    fwd.status == DnsRecord.STATUS_ENABLED,
                    fwd.type.in_(['A', 'AAAA']),
                    fwd.vrf_id == DnsRecord.vrf_id,
                    fwd.generated_ip == DnsRecord.generated_ip,
                )
                .exists()
            ),
        )
    ),
    info={
        'description': _(
            'PTR record must have at least one corresponding forward record with the same hostname and same IP address.'
        )
    },
)

RuleConstraint(
    name="dns_cname_on_dns_zone",
    model=DnsRecord,
    statement=(
        select(
            DnsRecord.id,
            DnsRecord.summary.label('name'),
        )
        .join(DnsZone, DnsRecord.name == DnsZone.name)
        .filter(
            DnsRecord.type == 'CNAME',
            DnsRecord.status == DnsRecord.STATUS_ENABLED,
        )
    ),
    info={
        'description': _('Alias for the canonical name (CNAME) should not be defined on a DNS Zone.'),
        'field': 'name',
        'related': lambda obj: DnsZone.query.filter(DnsZone.name == obj.name).first(),
    },
)


RuleConstraint(
    name="dns_cname_not_unique",
    model=DnsRecord,
    severity=Rule.SEVERITY_ENFORCED,
    statement=lambda: (
        (a := aliased(DnsRecord))
        and (
            select(
                DnsRecord.id,
                DnsRecord.summary.label('name'),
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
            .distinct()
        )
    ),
    info={
        'description': _('You cannot define other record type when an alias for a canonical name (CNAME) is defined.'),
        'related': lambda obj: DnsRecord.query.filter(
            DnsRecord.name == obj.name, DnsRecord.type != 'CNAME' if obj.type == 'CNAME' else DnsRecord.type == 'CNAME'
        ).first(),
    },
)

RuleConstraint(
    name='dns_soa_without_dns_zone',
    severity=Rule.SEVERITY_ENFORCED,
    model=DnsRecord,
    statement=select(DnsRecord.id.label('id'), DnsRecord.summary.label('name')).filter(
        DnsRecord.type == 'SOA',
        DnsRecord.status == DnsRecord.STATUS_ENABLED,
        ~(
            select(DnsZone.id)
            .filter(
                DnsZone.status == DnsZone.STATUS_ENABLED,
                DnsZone.name == DnsRecord.name,
            )
            .exists()
        ),
    ),
    info={
        'description': _('SOA record must be defined on DNS Zone.'),
        'field': 'name',
    },
)


RuleConstraint(
    name='dns_fwr_invalid_subnet_range',
    severity=Rule.SEVERITY_ENFORCED,
    model=DnsRecord,
    statement=select(DnsRecord.id.label('id'), DnsRecord.summary.label('name')).filter(
        DnsRecord.type.in_(['A', 'AAAA']),
        DnsRecord.status == DnsRecord.STATUS_ENABLED,
        ~(
            select(DnsZone.id)
            .join(DnsZone.subnets)
            .join(Subnet.subnet_ranges)
            .filter(
                DnsRecord.name.endswith(DnsZone.name),
                SubnetRange.version == func.family(DnsRecord.generated_ip),
                SubnetRange.start_ip <= DnsRecord.generated_ip,
                SubnetRange.end_ip >= DnsRecord.generated_ip,
                Subnet.vrf_id == DnsRecord.vrf_id,
                DnsZone.status == DnsZone.STATUS_ENABLED,
                Subnet.status == Subnet.STATUS_ENABLED,
            )
            .exists()
        ),
    ),
    info={
        'description': _('IP address must be defined within the DNS Zone.'),
        'field': 'value',
        'related': lambda obj: _collapse_subnet_ranges(
            DnsZone.query.with_entities(
                DnsZone.id.label('model_id'),
                literal(DnsZone.__tablename__).label('model_name'),
                func.group_concat(SubnetRange.range.text()).label('summary'),
            )
            .join(DnsZone.subnets)
            .join(Subnet.subnet_ranges)
            .filter(
                DnsZone.status == DnsZone.STATUS_ENABLED,
                Subnet.status == Subnet.STATUS_ENABLED,
                SubnetRange.version == (6 if obj.type == 'AAAA' else 4),
                literal(obj.name).endswith(DnsZone.name),
            )
            .group_by(DnsZone.id)
            .first()
        ),
    },
)

RuleConstraint(
    name='dns_ptr_invalid_subnet_range',
    severity=Rule.SEVERITY_ENFORCED,
    model=DnsRecord,
    statement=select(DnsRecord.id.label('id'), DnsRecord.summary.label('name')).filter(
        DnsRecord.type == 'PTR',
        DnsRecord.status == DnsRecord.STATUS_ENABLED,
        ~(
            select(DnsZone.id)
            .join(DnsZone.subnets)
            .join(Subnet.subnet_ranges)
            .filter(
                DnsRecord.value.endswith(DnsZone.name),
                SubnetRange.version == func.family(DnsRecord.generated_ip),
                SubnetRange.start_ip <= DnsRecord.generated_ip,
                SubnetRange.end_ip >= DnsRecord.generated_ip,
                Subnet.vrf_id == DnsRecord.vrf_id,
                DnsZone.status == DnsZone.STATUS_ENABLED,
                Subnet.status == Subnet.STATUS_ENABLED,
            )
            .exists()
        ),
    ),
    info={
        'description': _('IP address must be defined within the DNS Zone.'),
        'field': 'name',
        'related': lambda obj: _collapse_subnet_ranges(
            DnsZone.query.with_entities(
                DnsZone.id.label('model_id'),
                literal(DnsZone.__tablename__).label('model_name'),
                func.group_concat(SubnetRange.range.text()).label('summary'),
            )
            .join(DnsZone.subnets)
            .join(Subnet.subnet_ranges)
            .filter(
                DnsZone.status == DnsZone.STATUS_ENABLED,
                Subnet.status == Subnet.STATUS_ENABLED,
                SubnetRange.version == (6 if obj.name.endswith('.ip6.arpa') else 4),
                literal(obj.value).endswith(DnsZone.name),
            )
            .group_by(DnsZone.id)
            .first()
        ),
    },
)
