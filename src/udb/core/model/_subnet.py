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
from sqlalchemy import CheckConstraint, Column, Computed, ForeignKeyConstraint, Index, event, func
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import deferred, relationship, validates
from sqlalchemy.types import Boolean, Integer, SmallInteger, String

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.tools.i18n import gettext_lazy as _

from ._cidr import CidrType, InetType
from ._common import CommonMixin
from ._follower import FollowerMixin
from ._json import JsonMixin
from ._message import MessageMixin
from ._search_string import SearchableMixing
from ._status import StatusMixing
from ._vrf import Vrf

Base = cherrypy.tools.db.get_base()


Session = cherrypy.tools.db.get_session()


class SubnetRange(Base):
    __tablename__ = 'subnetrange'
    id = Column(Integer, primary_key=True)
    vrf_id = Column(Integer, nullable=False)
    # Define VRF relation as a view, since it not assignable and get updated by parent subnet.
    vrf = relationship(Vrf, primaryjoin=Vrf.id == vrf_id, foreign_keys="SubnetRange.vrf_id", viewonly=True)
    subnet_id = Column(Integer, nullable=False)
    subnet_estatus = Column(Integer, nullable=False)
    range = Column(CidrType, nullable=False)
    version = deferred(
        Column(
            SmallInteger,
            Computed(range.family(), persisted=True),
            index=True,
        )
    )
    start_ip = deferred(
        Column(
            InetType,
            Computed(func.inet(range.host()), persisted=True),
            index=True,
        )
    )
    end_ip = deferred(
        Column(
            InetType,
            Computed(func.inet(func.host(func.broadcast(range))), persisted=True),
            index=True,
        )
    )
    dhcp = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default='0',
    )
    dhcp_start_ip = Column(
        InetType,
        nullable=True,
    )
    dhcp_end_ip = Column(
        InetType,
        nullable=True,
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["vrf_id", "subnet_id", "subnet_estatus"],
            ["subnet.vrf_id", "subnet.id", "subnet.estatus"],
            onupdate="CASCADE",
        ),
        # Make sure DHCP start/end range is defined when DHCP is enabled
        CheckConstraint(
            "dhcp IS FALSE OR (dhcp_start_ip IS NOT NULL AND dhcp_end_ip IS NOT NULL)",
            name='dhcp_start_end_not_null',
        ),
        # Make sure DHCP start/end range are defined within CIDR
        CheckConstraint(
            "dhcp_start_ip IS NULL or dhcp_start_ip > start_ip",
            name='dhcp_start_ip_within_range',
        ),
        CheckConstraint(
            "dhcp_end_ip IS NULL or CASE WHEN version = 4 THEN dhcp_end_ip < end_ip ELSE dhcp_end_ip <= end_ip END",
            name='dhcp_end_ip_within_range',
        ),
        # Make sure DHCP start < end
        CheckConstraint(
            "dhcp_start_ip IS NULL or dhcp_end_ip IS NULL or dhcp_start_ip < dhcp_end_ip",
            name='dhcp_start_end_asc',
        ),
    )

    def __init__(self, range=None, **kwargs):
        """
        Special constructor for Association List
        """
        self.range = range
        super().__init__(range=range, **kwargs)

    @validates('range')
    def validate_range(self, key, value):
        # Validated at application level to avoid Postgresql raising exception
        if not value:
            return None
        try:
            return str(ipaddress.ip_network(value.strip(), strict=False))
        except (ValueError, AttributeError):
            # Repport error on 'ranges' instead of 'range'
            raise ValueError('ranges', "`%s` " % value + _('does not appear to be a valid IPv6 or IPv4 network'))

    def add_change(self, new_message):
        """
        When subnet range get modified, add the message to it's parent subnet.
        """
        assert new_message.changes, 'only message with changes should be append to subnet range'
        if not self.parent:
            # Parent is not defined when record get deleted,
            return
        if new_message.type == 'new':
            # When record get created, a changes is already added to parent subnet.
            return

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

        # Update message to be added to the parent.
        new_message.changes = {'subnet_ranges': [[old], [str(self)]]}
        self.parent.add_change(new_message)

    def __str__(self) -> str:
        """
        String representation used for audi log.
        """
        if self.dhcp:
            return '%s DHCP: %s - %s' % (self.range, self.dhcp_start_ip, self.dhcp_end_ip)
        return str(self.range)


Index(
    'subnetrange_vrf_id_range_unique_idx',
    SubnetRange.vrf_id,
    SubnetRange.range,
    unique=True,
    info={
        'description': _('This IP Range is already defined by another subnet.'),
        'field': 'range',
        # Specific message for subnet model_name.
        'subnet': {
            'description': _('This IP Range is already defined by another subnet.'),
            'field': 'subnet_ranges',
            'related': lambda obj: Subnet.query.join(Subnet.subnet_ranges)
            .filter(
                SubnetRange.vrf_id == obj.vrf_id,
                SubnetRange.range.in_([r.range for r in obj.subnet_ranges]),
                Subnet.id != obj.id,
            )
            .first(),
        },
    },
)

Index(
    'subnetrange_estatus_unique_idx',
    SubnetRange.id,
    SubnetRange.vrf_id,
    SubnetRange.subnet_id,
    SubnetRange.subnet_estatus,
    SubnetRange.range,
    unique=True,
)


class Subnet(CommonMixin, JsonMixin, StatusMixing, MessageMixin, FollowerMixin, SearchableMixing, Base):
    RIR_STATUS_ASSIGNED = "ASSIGNED"
    RIR_STATUS_ALLOCATED_BY_LIR = "ALLOCATED-BY-LIR"

    name = Column(String, nullable=False, default='')
    vrf_id = Column(Integer, nullable=False)
    vrf_estatus = Column(Integer, nullable=False)
    vrf = relationship(Vrf)
    l3vni = Column(Integer, nullable=True)
    l2vni = Column(Integer, nullable=True)
    vlan = Column(Integer, nullable=True)
    subnet_ranges = relationship(
        "SubnetRange",
        lazy=False,
        order_by=(SubnetRange.vrf_id, SubnetRange.version.desc(), SubnetRange.range),
        cascade="all, delete-orphan",
        backref="parent",
        active_history=True,
    )
    rir_status = Column(String, nullable=True, default=None)
    _subnet_string = Column(
        String,
        nullable=False,
        server_default='',
        doc="store string representation of the subnet ranges used for search",
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["vrf_id", "vrf_estatus"],
            ["vrf.id", "vrf.estatus"],
            onupdate="CASCADE",
        ),
    )

    # Transient fields for ordering
    depth = None
    order = None

    @classmethod
    def _search_string(cls):
        return cls.name + " " + cls.notes + " " + cls._subnet_string

    @classmethod
    def _estatus(cls):
        """
        Efective status computed based on status and vrf's status.
        """
        return [cls.status, cls.vrf_estatus]

    def _update_subnet_string(self):
        """
        Should be called everytime the record get insert or updated
        to make sure the subnet ranges are index for search.
        """
        self._subnet_string = ' '.join(r.range for r in self.subnet_ranges if r.range)

    def __str__(self):
        return "%s (%s)" % (', '.join(r.range for r in self.subnet_ranges if r.range), self.name)

    @hybrid_property
    def summary(self):
        return self.name

    def to_json(self):
        data = super().to_json()
        data['ranges'] = [r.range for r in self.subnet_ranges if r.range]
        data['subnet_ranges'] = [
            {
                'range': r.range,
                'dhcp': r.dhcp,
                'dhcp_start_ip': r.dhcp_start_ip,
                'dhcp_end_ip': r.dhcp_end_ip,
            }
            for r in self.subnet_ranges
        ]
        return data

    def from_json(self, data):
        subnet_ranges = data.pop('subnet_ranges', None)
        super().from_json(data)
        if subnet_ranges is not None:
            self.subnet_ranges = [SubnetRange(**r) for r in subnet_ranges]

    @validates('rir_status')
    def validate_rir_status(self, key, value):
        if not value:
            return None
        if value not in [Subnet.RIR_STATUS_ASSIGNED, Subnet.RIR_STATUS_ALLOCATED_BY_LIR]:
            raise ValueError('rir_status', "`%s` " % value + _('is not a valid RIR status'))
        return value

    def _validate(self):
        if not self.subnet_ranges:
            # you should probably use your own exception class here
            raise ValueError('ranges', _('at least one IPv6 or IPv4 network is required'))


@event.listens_for(Session, 'before_flush')
def subnet_before_flush(session, flush_context, instances):

    # TODO It all depends of the record status

    # When creating new DHCP Record, make sure to asign a SubnetRange and an IP
    for obj in itertools.chain(session.new, session.dirty):
        if isinstance(obj, Subnet):
            # Validate ranges.
            obj._validate()
            # Trigger update of subnet search string.
            obj._update_subnet_string()
            # Update VRF relationship
            if obj.attr_has_changes('vrf_id'):
                obj.vrf = Vrf.query.filter(Vrf.id == obj.vrf_id).first()


# Create a unique index subnet, vrf, estatus for foreignkey
Index(
    'subnet_estatus_unique_ix',
    Subnet.vrf_id,
    Subnet.id,
    Subnet.estatus,
    unique=True,
)
