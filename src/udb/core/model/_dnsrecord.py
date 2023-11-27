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
import itertools
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
    inspect,
    literal,
    or_,
    select,
    tuple_,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import aliased, declared_attr, foreign, relationship, remote, validates
from sqlalchemy.types import Integer, String

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.tools.i18n import gettext_lazy as _

from ._cidr import CidrType, InetType
from ._common import CommonMixin
from ._dnszone import NAME_PATTERN, DnsZone
from ._follower import FollowerMixin
from ._json import JsonMixin
from ._message import MessageMixin
from ._rule import Rule, RuleConstraint
from ._search_string import SearchableMixing
from ._status import StatusMixing
from ._subnet import Subnet, SubnetRange
from ._update import constraint_add, constraint_exists
from ._vrf import Vrf

Base = cherrypy.tools.db.get_base()

Session = cherrypy.tools.db.get_session()


def _collapse_subnet_ranges(obj):
    """
    Collapse the list of subnet range return by the query.
    """
    if not obj:
        return None

    a1 = aliased(DnsZone)
    ranges = (
        SubnetRange.query.with_entities(func.group_concat(SubnetRange.range.text()))
        .join(SubnetRange.parent)
        .join(Subnet.dnszones)
        .filter(
            DnsZone.id == a1.id,
            Subnet.estatus != Subnet.STATUS_DELETED,
            SubnetRange.version == (6 if obj.type == 'AAAA' or obj.name.endswith('.ip6.arpa') else 4),
        )
        .scalar_subquery()
    )
    zone = (
        a1.query.with_entities(
            a1.id.label('model_id'),
            literal(a1.__tablename__).label('model_name'),
            func.coalesce(ranges, a1.summary).label('summary'),
        )
        .filter(a1.estatus != DnsZone.STATUS_DELETED, _match_zone(literal(obj.name), a1.name))
        .first()
    )
    if zone is None:
        return None
    # Get list of range
    ranges = zone.summary.split(',')
    try:
        # Convert string to ip_network objects
        ranges = [ipaddress.ip_network(r) for r in ranges]
        # Combine the range
        combined_ranges = sorted(list(ipaddress.collapse_addresses(ranges)))
        # Replace original summary by our combined range
        new_obj = namedtuple('Row', ['model_id', 'model_name', 'summary'])
        return new_obj(
            zone.model_id,
            zone.model_name,
            ', '.join(map(str, combined_ranges)),
        )
    except ValueError:
        # Return original zone object if summary is not a subnet ranges.
        return zone


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


def _match_zone(name, zonename):
    if isinstance(name, str):
        name = literal(name)
    return or_(name == zonename, name.endswith('.' + zonename))


class DnsRecord(CommonMixin, JsonMixin, StatusMixing, MessageMixin, FollowerMixin, SearchableMixing, Base):

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

    # A DNS Record must be asigned to a specific VRF
    vrf_id = Column(Integer, ForeignKey("vrf.id"))
    vrf = relationship(Vrf)

    # A DNS Record must be created with a DNS Zone
    dnszone_id = Column(Integer)
    dnszone_name = Column(String)
    dnszone_estatus = Column(Integer)
    _dnszone = relationship(DnsZone)

    # A DNS Record must be created within a SubnetRange (A, AAAA, PTR)
    subnetrange_id = Column(Integer)
    subnet_id = Column(Integer)
    subnet_estatus = Column(Integer)
    subnetrange_range = Column(CidrType)
    _subnetrange = relationship(
        SubnetRange,
        overlaps="vrf",
        foreign_keys="[DnsRecord.subnetrange_id, DnsRecord.subnet_id, DnsRecord.subnet_estatus, DnsRecord.subnetrange_range]",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["generated_ip", "vrf_id"],
            ["ip.ip", "ip.vrf_id"],
            name="dnsrecord_ip_fk",
            info={
                'subnet': {
                    'description': _(
                        "Once DNS records have been created for a subnet range, it is not possible to update the VRF for this subnet."
                    ),
                    'related': lambda obj: DnsRecord.query.filter(DnsRecord.subnet_id == obj.id).limit(10).all(),
                },
            },
        ),
        # Use onupdate CASCADE to automatically update the status base on dnszone.
        ForeignKeyConstraint(
            ["dnszone_id", "dnszone_name", "dnszone_estatus"],
            ["dnszone.id", "dnszone.name", "dnszone.estatus"],
            onupdate="CASCADE",
            name="dnsrecord_dnszone_fk",
        ),
        # Use onupdate CASCADE to automatically update the status based on subnet and vrf status.
        ForeignKeyConstraint(
            [
                "subnetrange_id",
                "vrf_id",
                "subnet_id",
                "subnet_estatus",
                "subnetrange_range",
            ],
            [
                "subnetrange.id",
                "subnetrange.vrf_id",
                "subnetrange.subnet_id",
                "subnetrange.subnet_estatus",
                "subnetrange.range",
            ],
            onupdate="CASCADE",
            name="dnsrecord_subnetrange_fk",
            info={
                'subnet': {
                    'description': _(
                        "Once DNS records have been created for a subnet range, it is not possible to remove that subnet range."
                    ),
                    'related': lambda obj: DnsRecord.query.filter(DnsRecord.subnet_id == obj.id).limit(10).all(),
                },
            },
        ),
        # Make sure the Subnet is allowed within the DNS zone.
        ForeignKeyConstraint(
            ["subnet_id", "dnszone_id"],
            ["dnszone_subnet.subnet_id", "dnszone_subnet.dnszone_id"],
            name="dnsrecord_dnszone_subnet_fk",
            info={
                'subnet': {
                    'description': _(
                        "Once DNS records have been created for a subnet, it is not possible to remove the DNS Zone associated with that subnet range."
                    ),
                    'related': lambda obj: DnsRecord.query.filter(DnsRecord.subnet_id == obj.id).limit(10).all(),
                },
                'dnszone': {
                    'description': _(
                        "Once DNS records have been created for a DNS Zone, it is not possible to remove the subnet associated with that DNS Zone."
                    ),
                    'related': lambda obj: DnsRecord.query.filter(DnsRecord.dnszone_id == obj.id).limit(10).all(),
                },
            },
        ),
    )

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

    @classmethod
    def _estatus(cls):
        return [
            cls.status,
            func.coalesce(cls.subnet_estatus, Subnet.STATUS_ENABLED),
            func.coalesce(cls.dnszone_estatus, DnsZone.STATUS_ENABLED),
        ]

    def _get_related_dnszones(self):
        """
        Return DnsZone matching our name.
        """
        return (
            DnsZone.query.filter(
                or_(
                    _match_zone(self.hostname_value, DnsZone.name),
                    _match_zone(self.name, DnsZone.name),
                ),
                DnsZone.estatus != DnsZone.STATUS_DELETED,
            )
            .order_by(func.length(DnsZone.name))
            .all()
        )

    def related_dns_record_query(self):
        """
        Return a list of DNS Record with the same `hostname_value` excluding our self.
        """
        return DnsRecord.query.filter(
            DnsRecord.hostname_value == literal(self.hostname_value),
            DnsRecord.estatus != DnsRecord.STATUS_DELETED,
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
                DnsRecord.estatus != DnsRecord.STATUS_DELETED,
            ).first()
        elif self.type in ['A', 'AAAA']:
            value = ipaddress.ip_address(self.value).reverse_pointer
            return DnsRecord.query.filter(
                DnsRecord.type == 'PTR',
                DnsRecord.name == value,
                DnsRecord.value == self.name,
                DnsRecord.estatus != DnsRecord.STATUS_DELETED,
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
        raise ValueError(_('Can only create reverse DNS Record for PTR, A, AAAA types.'))

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

    @property
    def hostname_field(self):
        if self.type == 'PTR':
            return 'value'
        return 'name'

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

    @property
    def ip_field(self):
        if self.type == 'PTR':
            return 'name'
        elif self.type == 'A':
            return 'value'
        elif self.type == 'AAAA':
            return 'value'
        return None

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
            for dnszone in self._get_related_dnszones():
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

    def find_dnszone(self):
        """
        The parent DNS Zone for this record.
        """
        q = DnsZone.query.filter(
            _match_zone(self.name, remote(foreign(DnsZone.name))),
            DnsZone.estatus != DnsZone.STATUS_DELETED,
        ).order_by(-func.length(DnsZone.name))
        return q.first()

    def find_subnetrange(self):
        """
        Lookup database to find the best matching Subnet for this record.
        """
        q = (
            SubnetRange.query.join(SubnetRange.parent)
            .join(Subnet.dnszones)
            .filter(
                SubnetRange.version == func.family(literal(self.ip_value)),
                SubnetRange.start_ip <= func.inet(literal(self.ip_value)),
                SubnetRange.end_ip >= func.inet(literal(self.ip_value)),
                SubnetRange.subnet_estatus != Subnet.STATUS_DELETED,
            )
        )
        # If define, filter by VRF
        if self.vrf:
            q = q.filter(Subnet.vrf == self.vrf)
        # Filter by DNSZone
        if self._dnszone:
            q = q.filter(DnsZone.id == self._dnszone.id)
        return q.first()


@event.listens_for(DnsRecord.ip_value, 'set')
def dns_reload_ip(self, new_value, old_value, initiator):
    # When the ip address get updated on a record, make sure to load the relatd Ip object to update the history.
    if new_value != old_value:
        self._ip


# insert=True is required to run before messages hook.
@event.listens_for(Session, 'before_flush', insert=True)
def dnsrecord_assign_subnetrange(session, flush_context, instances):

    # When creating new DHCP Record, make sure to asign a SubnetRange and an IP
    for obj in itertools.chain(session.new, session.dirty):
        if isinstance(obj, DnsRecord):
            # Run default validation of field.
            obj._validate()

            # Dissociate the record from it's parent when getting deleted.
            if obj.status == DnsRecord.STATUS_DELETED:
                obj._dnszone = None
            elif obj.attr_has_changes(obj.hostname_field, 'status'):
                # Lookup dnszone
                obj._dnszone = obj.find_dnszone()

            # Disosiate the record from it's parent when getting deleted.
            if obj.status == DnsRecord.STATUS_DELETED:
                obj._subnetrange = None
            elif obj._dnszone and obj.ip_field:
                # Update subnetrange when vrf_id or IP address get updated.
                if obj.attr_has_changes('vrf', obj.ip_field, 'status'):
                    obj._subnetrange = obj.find_subnetrange()
            if obj._subnetrange is not None and obj.vrf != obj._subnetrange.vrf:
                obj.vrf = obj._subnetrange.vrf

            # Update relation to IP when vrf_id or ip get updated
            if obj.vrf and obj.ip_field and obj.attr_has_changes('vrf', obj.ip_field):
                from ._ip import Ip

                obj._ip  # Fetch record for history tracking
                obj._ip = Ip.unique_ip(session, obj.ip_value, obj.vrf.id)
            else:
                obj._ip = None


# `insert=True` is required to run before messages hook.
@event.listens_for(Session, 'after_flush', insert=True)
def dnsrecord_reassign_subnetrange(session, flush_context):
    # Collect all pair of subnet range & zone.
    pairs = set()
    for obj in itertools.chain(session.new, session.dirty):
        if isinstance(obj, Subnet) and obj.estatus != Subnet.STATUS_DELETED:
            for range in inspect(obj).attrs['subnet_ranges'].history.added or []:
                for zone in obj.dnszones:
                    pairs.add((range, zone))
            for zone in inspect(obj).attrs['dnszones'].history.added or []:
                for range in obj.subnet_ranges:
                    pairs.add((range, zone))
        elif isinstance(obj, DnsZone) and obj.estatus != DnsZone.STATUS_DELETED:
            # Use history tracker to get list of subnet added to the dns zone.
            for subnet in inspect(obj).attrs['subnets'].history.added or []:
                for range in subnet.subnet_ranges:
                    pairs.add((range, obj))

    # When subnet-range get update or created, make sure to re-assign the DNS Record accordingly.
    for range, zone in pairs:
        child = session.execute(
            select(SubnetRange.id)
            .join(SubnetRange.parent)
            .join(Subnet.dnszones)
            .filter(
                SubnetRange.id != range.id,
                SubnetRange.vrf_id == range.vrf_id,
                DnsZone.id == zone.id,
                func.subnet_of(SubnetRange.range, func.inet(range.range)),
                SubnetRange.subnet_estatus != Subnet.STATUS_DELETED,
            )
            .limit(1)
        ).first()
        if child:
            # Our current subnet range is not a "leaf" so we don't have anything to re-assign.
            continue
        # Our current subnet range is a new "leaf" we need to resign.
        subquery = (
            select(SubnetRange.id, SubnetRange.subnet_id, SubnetRange.subnet_estatus, SubnetRange.range)
            .filter(SubnetRange.id == range.id)
            .scalar_subquery()
        )
        session.execute(
            update(DnsRecord)
            .filter(
                DnsRecord.vrf_id == range.vrf_id,
                DnsRecord.dnszone_id == zone.id,
                DnsRecord.subnetrange_id != range.id,
                func.subnet_of(func.inet(DnsRecord.generated_ip), func.inet(range.range)),
                DnsRecord.type.in_(['A', 'AAAA', 'PTR']),
                DnsRecord.estatus != DnsRecord.STATUS_DELETED,
            )
            .values(
                {
                    tuple_(
                        DnsRecord.subnetrange_id,
                        DnsRecord.subnet_id,
                        DnsRecord.subnet_estatus,
                        DnsRecord.subnetrange_range,
                    ).self_group(): subquery
                }
            ),
            execution_options={'synchronize_session': False},
        )


# Make sure `type` only matches supported types.
CheckConstraint(
    DnsRecord.type.in_(DnsRecord.TYPES),
    name="dnsrecord_types_ck",
    info={
        'description': _('DNS record type not supported.'),
        'field': 'type',
    },
)

dnsrecord_dnszone_required_ck = CheckConstraint(
    or_(
        DnsRecord.status == DnsRecord.STATUS_DELETED,
        and_(
            DnsRecord.dnszone_id.is_not(None),
            DnsRecord.dnszone_name.is_not(None),
            DnsRecord.dnszone_estatus.is_not(None),
            _match_zone(DnsRecord.name, DnsRecord.dnszone_name),
        ),
    ),
    name="dnsrecord_dnszone_required_ck",
    info={
        'description': _('Hostname must be defined within a valid DNS Zone.'),
        'field': 'name',
        'dnszone': {
            'description': _("You can't change the DNS zone name once you've created a DNS record for it."),
            'field': 'name',
            'related': lambda obj: DnsRecord.query.filter(DnsRecord.dnszone_id == obj.id).limit(10).all(),
        },
    },
)

dnsrecord_subnetrange_required_ck = CheckConstraint(
    or_(
        DnsRecord.status == DnsRecord.STATUS_DELETED,
        DnsRecord.type.not_in(['A', 'AAAA', 'PTR']),
        and_(
            DnsRecord.vrf_id.is_not(None),
            DnsRecord.subnetrange_id.is_not(None),
            DnsRecord.subnet_id.is_not(None),
            DnsRecord.subnet_estatus.is_not(None),
            DnsRecord.subnetrange_range.is_not(None),
            func.subnet_of(DnsRecord.generated_ip, DnsRecord.subnetrange_range),
        ),
    ),
    name="dnsrecord_subnetrange_required_ck",
    info={
        'description': _(
            'The IP address {obj.ip_value} is not allowed in the DNS zone {obj.dnszone_name}. Consider modifying the list of authorized subnets for this zone.'
        ),
        'field': 'value',
        'related': _collapse_subnet_ranges,
        'subnet': {
            'description': _(
                "Once DNS records have been created for a subnet range, it is not possible to modify this range."
            ),
            'field': 'subnet_ranges',
            'related': lambda obj: DnsRecord.query.filter(DnsRecord.subnet_id == obj.id).limit(10).all(),
        },
    },
)

CheckConstraint(
    DnsRecord.value != '',
    name="dnsrecord_value_not_empty_ck",
    info={
        'description': _('value must not be empty'),
        'field': 'value',
    },
)

# When type is CNAME, PTR or NS, value must be a valid domain name.
CheckConstraint(
    or_(DnsRecord.type.not_in(['CNAME', 'NS', 'PTR']), DnsRecord.value.regexp_match(NAME_PATTERN.pattern)),
    name="dnsrecord_value_domain_name_ck",
    info={
        'description': _('value must be a valid domain name'),
        'field': 'value',
    },
)

# When type is A, AAAA value must be a valid IP.
CheckConstraint(
    or_(DnsRecord.type != 'A', and_(DnsRecord.generated_ip.is_not(None), func.family(DnsRecord.generated_ip) == 4)),
    name="dnsrecord_a_ip_value_ck",
    info={
        'description': _('value must be a valid IPv4 address'),
        'field': 'value',
    },
)

CheckConstraint(
    or_(DnsRecord.type != 'AAAA', and_(DnsRecord.generated_ip.is_not(None), func.family(DnsRecord.generated_ip) == 6)),
    name="dnsrecord_aaaa_ip_value_ck",
    info={
        'description': _('value must be a valid IPv6 address'),
        'field': 'value',
    },
)

CheckConstraint(
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
    name="dnsrecord_ptr_ip_value_ck",
    info={
        'description': _(
            'PTR records must ends with `.in-addr.arpa` or `.ip6.arpa` and define a valid IPv4 or IPv6 address'
        ),
        'field': 'name',
    },
)

CheckConstraint(
    or_(DnsRecord.type != 'SOA', DnsRecord.estatus == DnsZone.STATUS_DELETED, DnsRecord.dnszone_name == DnsRecord.name),
    name='dnsrecord_soa_dnszone_ck',
    info={
        'description': _('SOA record must be defined on DNS Zone.'),
        'field': 'name',
    },
)

# Make sure only one SOA record exists.
Index(
    'dnsrecord_soa_unique_ix',
    DnsRecord.name,
    unique=True,
    sqlite_where=and_(DnsRecord.type == 'SOA', DnsRecord.estatus != DnsRecord.STATUS_DELETED),
    postgresql_where=and_(DnsRecord.type == 'SOA', DnsRecord.estatus != DnsRecord.STATUS_DELETED),
    info={
        'description': _('An SOA record already exist for this domain.'),
        'field': 'name',
        'related': lambda obj: DnsRecord.query.filter(
            DnsRecord.type == 'SOA', DnsRecord.estatus != DnsRecord.STATUS_DELETED, DnsRecord.name == obj.name
        ).first(),
    },
)

RuleConstraint(
    name='dnsrecord_ptr_dnszone_required_rule',
    model=DnsRecord,
    severity=Rule.SEVERITY_SOFT,
    statement=select(DnsRecord.id.label('id'), DnsRecord.summary.label('name')).filter(
        # SOA and PTR are validated with another rule.
        DnsRecord.type == 'PTR',
        DnsRecord.estatus == DnsRecord.STATUS_ENABLED,
        ~(
            select(DnsZone.id)
            .filter(
                _match_zone(DnsRecord.name, DnsZone.name),
                DnsZone.estatus == DnsZone.STATUS_ENABLED,
            )
            .exists()
        ),
    ),
    info={
        'description': _('The value of the PTR record must be a hostname in a managed DNS zone.'),
        'field': 'value',
    },
)

RuleConstraint(
    name="dnsrecord_ptr_forward_required_rule",
    model=DnsRecord,
    statement=(
        lambda: (fwd := aliased(DnsRecord))
        and select(DnsRecord.id.label('id'), DnsRecord.summary.label('name'),).filter(
            DnsRecord.type == 'PTR',
            DnsRecord.estatus == DnsRecord.STATUS_ENABLED,
            ~(
                select(fwd.id)
                .filter(
                    fwd.estatus == DnsRecord.STATUS_ENABLED,
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
    name="dnsrecord_cname_dnszone_rule",
    model=DnsRecord,
    severity=Rule.SEVERITY_ENFORCED,
    statement=(
        select(DnsRecord.id, DnsRecord.summary.label('name'),).filter(
            DnsRecord.type == 'CNAME',
            DnsRecord.name == DnsRecord.dnszone_name,
            DnsRecord.estatus == DnsRecord.STATUS_ENABLED,
        )
    ),
    info={
        'description': _('Alias for the canonical name (CNAME) should not be defined on a DNS Zone.'),
        'field': 'name',
        'related': lambda obj: DnsZone.query.filter(DnsZone.name == obj.name).first(),
    },
)


RuleConstraint(
    name="dnsrecord_cname_unique_rule",
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
                DnsRecord.estatus == DnsRecord.STATUS_ENABLED,
                a.estatus == DnsRecord.STATUS_ENABLED,
            )
            .distinct()
        )
    ),
    info={
        'description': _('You cannot define other record type when an alias for a canonical name (CNAME) is defined.'),
        'related': lambda obj: DnsRecord.query.filter(
            DnsRecord.name == obj.name,
            DnsRecord.type != 'CNAME' if obj.type == 'CNAME' else DnsRecord.type == 'CNAME',
        ).first(),
    },
)


@event.listens_for(Base.metadata, 'after_create')
def create_missing_constraints(target, conn, **kw):
    if not constraint_exists(conn, dnsrecord_subnetrange_required_ck):
        constraint_add(conn, dnsrecord_subnetrange_required_ck)
    # Create new constraint.
    if not constraint_exists(conn, dnsrecord_dnszone_required_ck):
        constraint_add(conn, dnsrecord_subnetrange_required_ck)
