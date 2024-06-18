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

import cherrypy
import validators
from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    and_,
    event,
    func,
    insert,
    literal,
    literal_column,
    or_,
    select,
    tuple_,
    update,
)
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlalchemy.orm import aliased, declared_attr, foreign, relationship, remote, validates
from sqlalchemy.types import String

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.tools.i18n import gettext_lazy as _

from ._cidr import CidrType, InetType
from ._common import CommonMixin
from ._dnsrecord import DnsRecord
from ._events import listens_for_before_flush
from ._follower import FollowerMixin
from ._ip import Ip
from ._json import JsonMixin
from ._mac import Mac
from ._message import Message, MessageMixin
from ._rule import RuleConstraint
from ._search_string import SearchableMixing
from ._status import StatusMixing
from ._subnet import Subnet
from ._update import trigger_on_update
from ._vrf import Vrf

Base = cherrypy.tools.db.get_base()

Session = cherrypy.tools.db.get_session()


class DhcpRecord(CommonMixin, JsonMixin, StatusMixing, MessageMixin, FollowerMixin, SearchableMixing, Base):
    # Link to an IP (on a specific VRF)
    ip = Column(InetType, nullable=False)
    _ip = relationship(
        "Ip", back_populates='related_dhcp_records', lazy=True, foreign_keys="[DhcpRecord.ip, DhcpRecord.vrf_id]"
    )
    # Linked to a MAC
    mac = Column(String, ForeignKey("mac.mac"), nullable=False)
    _mac = relationship("Mac", backref='related_dhcp_records', lazy=True)
    # A DHCP Record must be asigned to a specific VRF
    vrf_id = Column(Integer, ForeignKey('vrf.id'), nullable=True)
    vrf = relationship(Vrf, overlaps="_ip", foreign_keys="[DhcpRecord.vrf_id]")
    # A DHCP Record must be created within a Subnet.
    subnet_id = Column(Integer)
    subnet_estatus = Column(Integer)
    subnet_range = Column(CidrType)
    _subnet = relationship(
        Subnet,
        overlaps="related_dhcp_records,vrf",
        foreign_keys="[DhcpRecord.subnet_id, DhcpRecord.subnet_estatus, DhcpRecord.subnet_range]",
    )

    __table_args__ = (
        # IP are unique per VRF.
        ForeignKeyConstraint(
            ["ip", "vrf_id"],
            ["ip.ip", "ip.vrf_id"],
            name='dhcprecord_ip_fk',
            info={
                'subnet': {
                    'description': _(
                        'Once DHCP reservation have been created for a subnet, it is not possible to update the VRF for this subnet.'
                    ),
                    'related': lambda obj: DhcpRecord.query.filter(DhcpRecord.subnet_id == obj.id).limit(10).all(),
                }
            },
        ),
        # Use onupdate CASCADE to automatically update the status based on subnet and vrf status.
        ForeignKeyConstraint(
            [
                "vrf_id",
                "subnet_id",
                "subnet_estatus",
                "subnet_range",
            ],
            [
                "subnet.vrf_id",
                "subnet.id",
                "subnet.estatus",
                "subnet.range",
            ],
            name='dhcprecord_subnet_fk',
            onupdate="CASCADE",
            info={
                'subnet': {
                    'description': _(
                        'Once DHCP reservation have been created for a subnet range, it is not possible to remove that range.'
                    ),
                    'related': lambda obj: DhcpRecord.query.filter(DhcpRecord.subnet_id == obj.id).limit(10).all(),
                }
            },
        ),
    )

    @classmethod
    def _search_string(cls):
        return cls.mac + " " + cls.notes

    @classmethod
    def _estatus(cls):
        return [cls.status, func.coalesce(cls.subnet_estatus, Subnet.STATUS_ENABLED)]

    @validates('ip')
    def validate_ip(self, key, value):
        # Validated at application level to avoid Postgresql raising exception
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            raise ValueError('ip', _('must be a valid IPv4 or IPv6 address'))

    @validates('mac')
    def validate_mac(self, key, value):
        # Validated at application level to avoid Postgresql raising exception
        if not validators.mac_address(value):
            raise ValueError('mac', _('expected a valid mac'))
        return value

    def __str__(self):
        return "%s (%s)" % (self.ip, self.mac)

    @hybrid_property
    def summary(self):
        return self.ip + " (" + self.mac + ")"

    @summary.expression
    def summary(self):
        return self.ip.host() + " (" + self.mac + ")"

    @declared_attr
    def related_dnsrecord(cls):
        return relationship(
            DnsRecord,
            primaryjoin=and_(
                remote(foreign(DnsRecord.generated_ip)) == cls.ip,
                remote(foreign(DnsRecord.vrf_id)) == cls.vrf_id,
                DnsRecord.type.in_(['PTR', 'A', 'AAAA']),
                DnsRecord.estatus != DnsRecord.STATUS_DELETED,
            ),
            lazy=True,
            viewonly=True,
        )

    @hybrid_method
    def _find_parent_subnet(cls, not_id=None):
        """
        Lookup database to find the best subnet range to be linked with this DHCP record.
        """
        query = Subnet.query.with_entities(Subnet.id, Subnet.estatus, Subnet.range).filter(
            func.subnet_of_or_equals(func.inet(cls.ip), Subnet.range),
            Subnet.estatus != DnsRecord.STATUS_DELETED,
        )
        # VRF is optional. Will pick first matching subnet.
        if isinstance(cls, type):
            query = query.filter(Subnet.vrf_id == cls.vrf_id)
        elif cls.vrf and cls.vrf.id:
            query = query.filter(Subnet.vrf_id == cls.vrf.id)
        if not_id:
            query = query.filter(Subnet.id != not_id)
        return query.order_by(Subnet.range.desc()).limit(1)

    def add_change(self, new_message):
        # Strip subnet_id from history because we only want to display subnet's name.
        if 'subnet_id' in new_message.changes:
            new_message.changes = {key: value for key, value in new_message.changes.items() if key != 'subnet_id'}
        super().add_change(new_message)


Index(
    'dhcprecord_mac_unique_ix',
    DhcpRecord.mac,
    unique=True,
    sqlite_where=DhcpRecord.estatus != DhcpRecord.STATUS_DELETED,
    postgresql_where=DhcpRecord.estatus != DhcpRecord.STATUS_DELETED,
    info={
        'description': _('A DHCP Reservation already exists for this MAC address.'),
        'field': 'mac',
        'related': lambda obj: DhcpRecord.query.filter(
            DhcpRecord.estatus != DhcpRecord.STATUS_DELETED, DhcpRecord.mac == obj.mac
        ).first(),
    },
)


@event.listens_for(DhcpRecord.ip, 'set')
def dhcp_reload_ip(self, new_value, old_value, initiator):
    # When the IP address get updated on a record, make sure to load the related Ip object to update the history.
    if new_value != old_value:
        self._ip


@event.listens_for(DhcpRecord.mac, 'set')
def dns_reload_mac(self, new_value, old_value, initiator):
    # When the MAC address get updated on a record, make sure to load the related MAC object to update the history.
    if new_value != old_value:
        self._mac


CheckConstraint(
    or_(
        DhcpRecord.status == DhcpRecord.STATUS_DELETED,
        and_(
            DhcpRecord.vrf_id.is_not(None),
            DhcpRecord.subnet_id.is_not(None),
            DhcpRecord.subnet_estatus.is_not(None),
            DhcpRecord.subnet_range.is_not(None),
            func.subnet_of_or_equals(DhcpRecord.ip, DhcpRecord.subnet_range),
        ),
    ),
    name="dhcprecord_subnet_required_ck",
    info={
        'description': _("The IP address {obj.ip} is not allowed in any subnet."),
        'field': 'ip',
        'subnet': {
            'description': _(
                'Once DHCP reservation have been created for a subnet range, it is not possible to modify that range.'
            ),
            'field': 'slave_subnets',
            'related': lambda obj: DhcpRecord.query.filter(DhcpRecord.subnet_id == obj.id).limit(10).all(),
        },
    },
)

RuleConstraint(
    name="dhcprecord_invalid_subnet_rule",
    model=DhcpRecord,
    statement=select(
        DhcpRecord.id.label('id'),
        DhcpRecord.summary.label('name'),
    )
    .join(DhcpRecord._subnet)
    .filter(Subnet.dhcp.is_(False), DhcpRecord.estatus == DhcpRecord.STATUS_ENABLED),
    info={
        'description': _("The subnet for this DHCP is currently disabled."),
        'field': 'ip',
    },
)

RuleConstraint(
    name="dhcprecord_unique_ip_rule",
    model=DhcpRecord,
    statement=(
        lambda: (a := aliased(DhcpRecord))
        and (
            select(
                DhcpRecord.id.label('id'),
                DhcpRecord.summary.label('name'),
            )
            .join(a, and_(DhcpRecord.ip == a.ip, DhcpRecord.vrf_id == a.vrf_id))
            .filter(
                DhcpRecord.id != a.id,
                DhcpRecord.estatus == DhcpRecord.STATUS_ENABLED,
                a.estatus == DhcpRecord.STATUS_ENABLED,
            )
            .distinct()
        )
    ),
    info={
        'description': _('Multiple DHCP Reservation for the same IP address within the same VRF.'),
        'field': 'ip',
    },
)


@listens_for_before_flush(DhcpRecord)
def dhcprecord_before_flush(session, flush_context, obj):
    # When creating new DHCP Record, make sure to assign a Subnet range and an IP
    # Dissosiate the record from it's parent when getting deleted.
    if obj.status == DhcpRecord.STATUS_DELETED:
        obj._subnet = None
    elif obj.attr_has_changes('vrf', 'ip', 'status'):
        # Update subnetrange when vrf_id or IP address get updated.
        parent = obj._find_parent_subnet().add_columns(Subnet.vrf_id).first()
        obj.subnet_id = parent.id if parent else None
        obj.subnet_estatus = parent.estatus if parent else None
        obj.subnet_range = parent.range if parent else None
        obj.vrf = Vrf.query.filter(Vrf.id == parent.vrf_id).first() if parent else None

    # Update relation to IP when vrf_id or ip get updated
    if obj.attr_has_changes('vrf', 'ip') and obj.ip is not None and obj.vrf is not None:
        obj._ip  # Fetch record for history tracking
        obj._ip = Ip.unique_ip(session, obj.ip, obj.vrf)

    if obj.attr_has_changes('mac'):
        obj._mac  # Fetch record for history tracking
        obj._mac = Mac.unique_mac(session, obj.mac)


@event.listens_for(Subnet, 'after_update')
@event.listens_for(Subnet, 'after_insert')
def dhcprecord_subnet_after_update(mapper, conn, subnet):
    if subnet.estatus != Subnet.STATUS_DELETED:
        # When subnet-range get update or created, make sure to re-assign the DHCP accordingly.
        assign_dhcprecord = (
            update(DhcpRecord)
            .inline()
            .filter(
                DhcpRecord.vrf_id == subnet.vrf_id,
                func.subnet_of_or_equals(DhcpRecord.ip, subnet.range),
                DhcpRecord.estatus != Subnet.STATUS_DELETED,
            )
            .values(
                {
                    tuple_(
                        DhcpRecord.subnet_id,
                        DhcpRecord.subnet_estatus,
                        DhcpRecord.subnet_range,
                    )
                    .self_group(): DhcpRecord._find_parent_subnet()
                    .scalar_subquery(),
                }
            )
        )
        conn.execute(assign_dhcprecord, execution_options={'synchronize_session': False})


@event.listens_for(Base.metadata, 'after_create')
def dhcprecord_subnet_range_trigger(target, conn, **kw):
    """
    This create a trigger for dhcprecord to keep track when parent get updated.
    """
    insert_message = (
        insert(Message)
        .inline()
        .values(
            {
                Message.model_name: 'dhcprecord',
                Message.model_id: literal_column('new.id'),
                Message.type: 'parent',
                Message.body: '',
                Message._changes: literal('{"subnet_range": ["')
                + func.text(literal_column('old.subnet_range'))
                + literal('", "')
                + func.text(literal_column('new.subnet_range'))
                + literal('"]}'),
                Message.author_id: None,
            }
        )
    )
    trigger_on_update(conn, 'dhcprecord_subnet_range_trigger', columns=[DhcpRecord.subnet_range], sql=insert_message)


@event.listens_for(Base.metadata, 'after_create')
def dhcprecord_subnet_estatus_trigger(target, conn, **kw):
    """
    This create a trigger for dhcprecord to keep track of changes made on parent subnet.
    """
    insert_message = (
        insert(Message)
        .inline()
        .values(
            {
                Message.model_name: 'dhcprecord',
                Message.model_id: literal_column('new.id'),
                Message.type: 'parent',
                Message.body: '',
                Message._changes: literal('{"subnet_estatus": [')
                + literal_column('old.subnet_estatus')
                + literal(',')
                + literal_column('new.subnet_estatus')
                + literal(']}'),
                Message.author_id: None,
            }
        )
    )
    trigger_on_update(
        conn, 'dhcprecord_subnet_estatus_trigger', columns=[DhcpRecord.subnet_estatus], sql=insert_message
    )
