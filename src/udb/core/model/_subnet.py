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
from sqlalchemy import CheckConstraint, Column, Computed, ForeignKey, ForeignKeyConstraint, Index, event, func
from sqlalchemy.ext.associationproxy import association_proxy
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


class SubnetRange(Base):
    __tablename__ = 'subnetrange'
    id = Column(Integer, primary_key=True)
    subnet_id = Column(Integer, nullable=False)
    vrf_id = Column(Integer, nullable=False)
    range = Column(CidrType, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(["subnet_id", "vrf_id"], ["subnet.id", "subnet.vrf_id"], onupdate="CASCADE"),
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
            "dhcp_start_ip IS NULL or dhcp_end_ip IS NULL or dhcp_start_ip < dhcp_end_ip", name='dhcp_start_end_asc'
        ),
    )
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

    def __init__(self, range=None, **kwargs):
        """
        Special constructor for Association List
        """
        self.range = range
        super().__init__(range=range, **kwargs)

    @validates('range')
    def validate_range(self, key, value):
        if not value:
            return None
        try:
            return str(ipaddress.ip_network(value.strip(), strict=False))
        except (ValueError, AttributeError):
            # Repport error on 'ranges' instead of 'range'
            raise ValueError('ranges', "`%s` " % value + _('does not appear to be a valid IPv6 or IPv4 network'))

    def __str__(self) -> str:
        return self.range


# Create a unique index for username
subnetrange_index = Index('subnetrange_index', SubnetRange.vrf_id, SubnetRange.range, unique=True)

# Index for cidr sorting
subnetrange_order = Index('subnetrange_order', SubnetRange.vrf_id, SubnetRange.version.desc(), SubnetRange.range)


class Subnet(CommonMixin, JsonMixin, StatusMixing, MessageMixin, FollowerMixin, SearchableMixing, Base):
    RIR_STATUS_ASSIGNED = "ASSIGNED"
    RIR_STATUS_ALLOCATED_BY_LIR = "ALLOCATED-BY-LIR"

    name = Column(String, nullable=False, default='')
    vrf_id = Column(Integer, ForeignKey("vrf.id"), nullable=False)
    vrf = relationship(Vrf)
    l3vni = Column(Integer, nullable=True)
    l2vni = Column(Integer, nullable=True)
    vlan = Column(Integer, nullable=True)
    subnet_ranges = relationship(
        "SubnetRange",
        lazy=False,
        order_by=(SubnetRange.vrf_id, SubnetRange.version.desc(), SubnetRange.range),
        cascade="all, delete-orphan",
    )
    ranges = association_proxy("subnet_ranges", "range")
    rir_status = Column(String, nullable=True, default=None)
    _subnet_string = Column(
        String,
        nullable=False,
        server_default='',
        doc="store string representation of the subnet ranges used for search",
    )

    # Transient fields for ordering
    depth = None
    order = None

    @classmethod
    def _search_string(cls):
        return cls.name + " " + cls.notes + " " + cls._subnet_string

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

    @validates('rir_status')
    def validate_rir_status(self, key, value):
        if not value:
            return None
        if value not in [Subnet.RIR_STATUS_ASSIGNED, Subnet.RIR_STATUS_ALLOCATED_BY_LIR]:
            raise ValueError('rir_status', "`%s` " % value + _('is not a valid RIR status'))
        return value


@event.listens_for(Subnet, 'before_insert')
@event.listens_for(Subnet, 'before_update')
def receive_before_insert_or_update(mapper, connection, subnet):

    if not subnet.subnet_ranges:
        # you should probably use your own exception class here
        raise ValueError('ranges', _('at least one IPv6 or IPv4 network is required'))

    # Trigger update of subnet search string.
    subnet._update_subnet_string()


# Create a unique index subnet & vrf
Index('subnet_vrf_index', Subnet.id, Subnet.vrf_id, unique=True)
