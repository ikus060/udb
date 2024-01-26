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

import cherrypy
from sqlalchemy import (
    CheckConstraint,
    Column,
    Computed,
    ForeignKeyConstraint,
    Index,
    and_,
    case,
    event,
    func,
    or_,
    tuple_,
    update,
)
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlalchemy.orm import aliased, relationship, validates
from sqlalchemy.types import Boolean, Integer, String

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.tools.i18n import gettext_lazy as _

from ._cidr import CidrType, InetType
from ._common import CommonMixin
from ._follower import FollowerMixin
from ._json import JsonMixin
from ._message import MessageMixin
from ._network_id import NetworkId
from ._search_string import SearchableMixing
from ._status import StatusMixing
from ._vrf import Vrf

Base = cherrypy.tools.db.get_base()


Session = cherrypy.tools.db.get_session()


class Subnet(CommonMixin, JsonMixin, StatusMixing, MessageMixin, FollowerMixin, SearchableMixing, Base):
    RIR_STATUS_ASSIGNED = "ASSIGNED"
    RIR_STATUS_ALLOCATED_BY_LIR = "ALLOCATED-BY-LIR"

    # Fields
    name = Column(String, nullable=False, default='')
    vlan = Column(NetworkId, nullable=False, default=NetworkId.UNDEFINED, server_default=str(NetworkId.UNDEFINED))
    l3vni = Column(NetworkId, nullable=False, default=NetworkId.UNDEFINED, server_default=str(NetworkId.UNDEFINED))
    l2vni = Column(NetworkId, nullable=False, default=NetworkId.UNDEFINED, server_default=str(NetworkId.UNDEFINED))
    range = Column(CidrType, nullable=False)
    rir_status = Column(String, nullable=True, default=None)
    dhcp = Column(Boolean, nullable=False, default=False, server_default='0')
    dhcp_start_ip = Column(InetType, nullable=True)
    dhcp_end_ip = Column(InetType, nullable=True)

    # VRF
    vrf_id = Column(Integer, nullable=False)
    vrf_estatus = Column(Integer, nullable=False)
    vrf = relationship(Vrf)

    # Parent/Slave Range
    slave = Column(Boolean, nullable=False, default=False, server_default="False")
    parent_id = Column(Integer, nullable=True)
    parent_evlan = Column(NetworkId, nullable=True)
    parent_el2vni = Column(NetworkId, nullable=True)
    parent_el3vni = Column(NetworkId, nullable=True)
    parent_estatus = Column(Integer, nullable=True)
    parent_range = Column(CidrType, nullable=True)
    parent_depth = Column(Integer, nullable=True)

    # Inherited fields value
    evlan = Column(
        NetworkId,
        Computed(
            case(
                (vlan != NetworkId.UNDEFINED, vlan),
                (parent_evlan.is_not(None), parent_evlan),
                else_=NetworkId.UNDEFINED,
            )
        ),
    )
    el2vni = Column(
        NetworkId,
        Computed(
            case(
                (l2vni != NetworkId.UNDEFINED, l2vni),
                (parent_el2vni.is_not(None), parent_el2vni),
                else_=NetworkId.UNDEFINED,
            )
        ),
    )
    el3vni = Column(
        NetworkId,
        Computed(
            case(
                (l3vni != NetworkId.UNDEFINED, l3vni),
                (parent_el3vni.is_not(None), parent_el3vni),
                else_=NetworkId.UNDEFINED,
            )
        ),
    )
    depth = Column(Integer, Computed(case((parent_depth.is_not(None), parent_depth + 1), else_=0)), nullable=False)

    # Parent, child & slaves relation-ship
    master = relationship(
        "Subnet",
        primaryjoin="and_(Subnet.parent_id == remote(Subnet.id), Subnet.parent_evlan == remote(Subnet.evlan), Subnet.parent_el2vni == remote(Subnet.el2vni), Subnet.parent_el3vni==remote(Subnet.el3vni), Subnet.parent_estatus==remote(Subnet.estatus), Subnet.parent_range==remote(Subnet.range), Subnet.parent_depth==remote(Subnet.depth), Subnet.slave == True)",
        back_populates='slave_subnets',
        lazy=True,
    )
    slave_subnets = relationship(
        "Subnet",
        primaryjoin="and_(remote(Subnet.parent_id) == Subnet.id, remote(Subnet.parent_evlan) == Subnet.evlan, remote(Subnet.parent_el2vni) == Subnet.el2vni, remote(Subnet.parent_el3vni)==Subnet.el3vni, remote(Subnet.parent_estatus)==Subnet.estatus, remote(Subnet.parent_range)==Subnet.range, remote(Subnet.parent_depth)==Subnet.depth, remote(Subnet.slave) == True)",
        back_populates='master',
        lazy=True,
    )

    _subnet_string = Column(
        String,
        nullable=False,
        server_default='',
        doc="store string representation of the subnet ranges used for search",
    )

    __table_args__ = (
        # Index for parent child inheritance.
        Index(
            'subnet_parent_childs_slaves_unique_ix',
            'vrf_id',
            'id',
            'evlan',
            'el2vni',
            'el3vni',
            'estatus',
            'range',
            'depth',
            unique=True,
        ),
        # ForeignKey to VRF
        ForeignKeyConstraint(
            ["vrf_id", "vrf_estatus"],
            ["vrf.id", "vrf.estatus"],
            name='subnet_vrf_fk',
            onupdate="CASCADE",
        ),
        # ForeignKey for parent childs & slaves
        ForeignKeyConstraint(
            [
                "vrf_id",
                "parent_id",
                "parent_evlan",
                "parent_el2vni",
                "parent_el3vni",
                "parent_estatus",
                "parent_range",
                "parent_depth",
            ],
            [
                "subnet.vrf_id",
                "subnet.id",
                "subnet.evlan",
                "subnet.el2vni",
                "subnet.el3vni",
                "subnet.estatus",
                "subnet.range",
                "subnet.depth",
            ],
            name='subnet_parent_fk',
            onupdate="CASCADE",
            use_alter=True,
        ),
        # Make sure DHCP start/end range is defined when DHCP is enabled
        CheckConstraint(
            "dhcp IS FALSE OR (dhcp_start_ip IS NOT NULL AND dhcp_end_ip IS NOT NULL)",
            name='dhcp_start_end_not_null',
        ),
        # Make sure DHCP start/end range are defined within CIDR
        CheckConstraint(
            or_(dhcp_start_ip.is_(None), func.inet(func.host(range)) < dhcp_start_ip),
            name='dhcp_start_ip_within_range',
        ),
        CheckConstraint(
            or_(
                dhcp_end_ip.is_(None),
                case(
                    (func.family(range) == 4, dhcp_end_ip < func.inet(func.host(func.broadcast(range)))),
                    else_=dhcp_end_ip <= func.inet(func.host(func.broadcast(range))),
                ),
            ),
            name='dhcp_end_ip_within_range',
        ),
        # Make sure DHCP start < end
        CheckConstraint(
            or_(dhcp_start_ip.is_(None), dhcp_end_ip.is_(None), dhcp_start_ip < dhcp_end_ip),
            name='dhcp_start_end_asc',
        ),
    )

    @classmethod
    def _search_string(cls):
        return cls.name + " " + cls.notes + " " + func.text(cls.range) + " " + cls._subnet_string

    @classmethod
    def _estatus(cls):
        """
        Efective status computed based on status and vrf's status.
        """
        return [
            cls.status,
            func.coalesce(cls.vrf_estatus, Vrf.STATUS_ENABLED),
            func.coalesce(cls.parent_estatus, Vrf.STATUS_ENABLED),
        ]

    def _update_subnet_string(self):
        """
        Should be called everytime the record get insert or updated
        to make sure the subnet ranges are index for search.
        """
        if self.slave_subnets:
            self._subnet_string = ' '.join(r.range for r in self.slave_subnets if r.range)
        else:
            self._subnet_string = ''

    def __str__(self):
        if self.dhcp:
            return '%s DHCP: %s - %s' % (self.range, self.dhcp_start_ip, self.dhcp_end_ip)
        return str(self.range)

    @hybrid_property
    def summary(self):
        return self.name

    def to_json(self):
        return {
            'id': self.id,
            'name': self.name,
            'vrf_id': self.vrf_id,
            'vlan': self.evlan,
            'l3vni': self.el3vni,
            'l2vni': self.el2vni,
            'range': self.range,
            'dhcp': self.dhcp,
            'dhcp_start_ip': self.dhcp_start_ip,
            'dhcp_end_ip': self.dhcp_end_ip,
            'slave_subnets': [
                {
                    'range': r.range,
                    'dhcp': r.dhcp,
                    'dhcp_start_ip': r.dhcp_start_ip,
                    'dhcp_end_ip': r.dhcp_end_ip,
                }
                for r in self.slave_subnets
            ],
            'rir_status': self.rir_status,
            'depth': self.depth,
            'owner_id': self.owner_id,
            'status': self.estatus,
            'notes': self.notes,
        }

    def from_json(self, data):
        slave_subnets = data.pop('slave_subnets', None)
        super().from_json(data)
        if slave_subnets is not None:
            self.slave_subnets = [Subnet(**r) for r in slave_subnets]

    @validates('range')
    def validate_range(self, key, value):
        # Validated at application level to avoid Postgresql raising exception
        if not value:
            return None
        try:
            return str(ipaddress.ip_network(value.strip(), strict=False))
        except (ValueError, AttributeError):
            raise ValueError('range', "`%s` " % value + _('does not appear to be a valid IPv6 or IPv4 network'))

    @validates('rir_status')
    def validate_rir_status(self, key, value):
        if not value:
            return None
        if value not in [Subnet.RIR_STATUS_ASSIGNED, Subnet.RIR_STATUS_ALLOCATED_BY_LIR]:
            raise ValueError('rir_status', "`%s` " % value + _('is not a valid RIR status'))
        return value

    @hybrid_method
    def _find_parent(cls, not_id=None):
        """Subquery to find imediate parent of Subnet."""
        p1 = aliased(Subnet)
        query = p1.query.with_entities(p1.id, p1.evlan, p1.el2vni, p1.el3vni, p1.estatus, p1.range, p1.depth).filter(
            func.subnet_of(cls.range, p1.range),
            p1.estatus != Subnet.STATUS_DELETED,
        )
        if cls.id:
            query = query.filter(p1.id != cls.id)
        assert cls.vrf_id or cls.vrf.id, 'vrf_id or vrf is required for this query'
        query = query.filter(p1.vrf_id == (cls.vrf_id or cls.vrf.id))
        if not_id:
            query = query.filter(p1.id != not_id)
        return query.order_by(p1.range.desc()).limit(1)

    def add_change(self, new_message):
        """
        When slave subnet get modified, add the message to it's parent subnet.
        """
        if new_message.type != 'new' and self.slave and self.master:
            # Format an old representation of the range
            old_values = {k: v[0] for k, v in new_message.changes.items()}
            if old_values.get('dhcp', self.dhcp):
                old = '%s DHCP: %s - %s' % (
                    old_values.get('range', self.range),
                    old_values.get('dhcp_start_ip', self.dhcp_start_ip),
                    old_values.get('dhcp_end_ip', self.dhcp_end_ip),
                )
            else:
                old = str(old_values.get('range', self.range))
            if self.dhcp:
                new = '%s DHCP: %s - %s' % (self.range, self.dhcp_start_ip, self.dhcp_end_ip)
            else:
                new = str(self.range)
            # Update message to be added to the parent.
            if old != new:
                new_message.changes = {'slave_subnets': [[old], [new]]}
                self.master.add_change(new_message)
        else:
            super().add_change(new_message)


# Create a unique index subnet, vrf, estatus for foreignkey
Index(
    'subnet_estatus_unique_ix',
    Subnet.vrf_id,
    Subnet.id,
    Subnet.estatus,
    Subnet.range,
    unique=True,
)

Index(
    'subnet_vrf_id_range_unique_idx',
    Subnet.vrf_id,
    Subnet.range,
    unique=True,
    info={
        'description': _('This IP Range is already defined by another subnet.'),
        'field': 'ranges',
        'related': lambda obj: Subnet.query.filter(
            Subnet.vrf_id == obj.vrf_id,
            or_(
                and_(Subnet.id != obj.id, Subnet.range == obj.range),
                *[and_(Subnet.id != slave.id, Subnet.range == slave.range) for slave in obj.slave_subnets]
            ),
        ).first(),
    },
)

CheckConstraint(
    or_(Subnet.parent_id.is_(None), Subnet.id != Subnet.parent_id),
    name="subnet_parent_id_ck",
)
# Parent's subnet must include child subnet.
CheckConstraint(
    or_(Subnet.slave, Subnet.parent_range.is_(None), func.subnet_of(Subnet.range, Subnet.parent_range)),
    name="subnet_parent_range_ck",
)
# A Slave need a parent.
CheckConstraint(
    or_(Subnet.slave.is_(False), Subnet.parent_id.is_not(None)),
    name="subnet_slave_parent_ck",
)


@event.listens_for(Session, 'before_flush', insert=True)
def subnet_before_flush(session, flush_context, instances):
    for obj in itertools.chain(session.new, session.dirty):
        if isinstance(obj, Subnet):
            # Trigger update of subnet search string.
            obj._update_subnet_string()
            # Update VRF relationship from vrf_id - This is required for JSON API
            if obj.attr_has_changes('vrf_id'):
                obj.vrf = Vrf.query.filter(Vrf.id == obj.vrf_id).first()
            # Copy some of parent attributes to slaves.
            for slave in obj.slave_subnets:
                slave.name = obj.name
                slave.vrf = obj.vrf
                slave.slave = True
                slave.dnszones = obj.dnszones


@event.listens_for(Subnet, 'before_insert')
@event.listens_for(Subnet, 'before_update')
def subnet_before_insert(mapper, conn, obj):
    if obj.estatus != Subnet.STATUS_DELETED and obj.attr_has_changes('vrf', 'range'):
        #
        # 1. When a subnet get inserted or updated, we need to find it's parent if it's not a slave.
        #
        if not obj.slave:
            new_parent = obj._find_parent().first()
            obj.parent_id = new_parent.id if new_parent else None
            obj.parent_evlan = new_parent.evlan if new_parent else None
            obj.parent_el2vni = new_parent.el2vni if new_parent else None
            obj.parent_el3vni = new_parent.el3vni if new_parent else None
            obj.parent_estatus = new_parent.estatus if new_parent else None
            obj.parent_range = new_parent.range if new_parent else None
            obj.parent_depth = new_parent.depth if new_parent else None
        #
        # 2. When a parent get updated, we need to re-assigned childrens to another parent.
        #
        if obj.id:
            unassign_children = (
                update(Subnet)
                .filter(
                    Subnet.id != obj.id,
                    Subnet.slave.is_(False),
                    Subnet.vrf_id == obj.vrf_id,
                    Subnet.parent_id == obj.id,
                    Subnet.estatus != Subnet.STATUS_DELETED,
                )
                .values(
                    {
                        tuple_(
                            Subnet.parent_id,
                            Subnet.parent_evlan,
                            Subnet.parent_el2vni,
                            Subnet.parent_el3vni,
                            Subnet.parent_estatus,
                            Subnet.parent_range,
                            Subnet.parent_depth,
                        )
                        .self_group(): Subnet._find_parent(not_id=obj.id)
                        .scalar_subquery()
                    }
                )
            )
            conn.execute(unassign_children, execution_options={'synchronize_session': False})


@event.listens_for(Session, 'after_flush', insert=True)
def subnet_after_flush(session, flush_context):
    for obj in itertools.chain(session.new, session.dirty):
        if isinstance(obj, Subnet) and obj.estatus != Subnet.STATUS_DELETED and obj.attr_has_changes('vrf', 'range'):
            #
            # 1. When a subnet get inserted or updated, we need to re-assign children subnet to our new subnet.
            #
            assign_children = (
                update(Subnet)
                .filter(
                    Subnet.id != obj.id,
                    Subnet.slave.is_(False),
                    Subnet.vrf_id == obj.vrf_id,
                    func.subnet_of(Subnet.range, obj.range),
                    Subnet.estatus != Subnet.STATUS_DELETED,
                    # TODO Is this required ? Determine if the parent is our new/updated record.
                    # literal_column('new.id') == find_parent.with_entities(p1.id),
                )
                .values(
                    {
                        tuple_(
                            Subnet.parent_id,
                            Subnet.parent_evlan,
                            Subnet.parent_el2vni,
                            Subnet.parent_el3vni,
                            Subnet.parent_estatus,
                            Subnet.parent_range,
                            Subnet.parent_depth,
                        )
                        .self_group(): Subnet._find_parent()
                        .scalar_subquery()
                    }
                )
            )
            session.execute(assign_children, execution_options={'synchronize_session': False})
