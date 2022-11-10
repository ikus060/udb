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
from sqlalchemy import Column, ForeignKey, ForeignKeyConstraint, Index, event
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import defer, joinedload, raiseload, relationship, undefer, validates
from sqlalchemy.types import Integer, String

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.tools.i18n import gettext_lazy as _

from ._cidr import CidrType
from ._common import CommonMixin
from ._vrf import Vrf

Base = cherrypy.tools.db.get_base()


class SubnetRange(Base):
    __tablename__ = 'subnetrange'
    id = Column(Integer, primary_key=True)
    subnet_id = Column(Integer, nullable=False)
    vrf_id = Column(Integer, nullable=False)
    range = Column(CidrType)
    __table_args__ = (
        ForeignKeyConstraint(["subnet_id", "vrf_id"], ["subnet.id", "subnet.vrf_id"], onupdate="CASCADE"),
    )

    def __init__(self, range=None):
        """
        Special constructor for Association List
        """
        self.range = range

    @validates('range')
    def validate_range(self, key, value):
        if not value:
            return None
        try:
            return str(ipaddress.ip_network(value.strip(), strict=False))
        except (ValueError, AttributeError):
            # Repport error on 'ranges' instead of 'range'
            raise ValueError('ranges', "`%s` " % value + _('does not appear to be a valid IPv6 or IPv4 network'))

    @property
    def version(self):
        return ipaddress.ip_network(self.range).version

    def subnet_of(self, other):
        return ipaddress.ip_network(self.range).subnet_of(ipaddress.ip_network(other.range))

    def __str__(self) -> str:
        return self.range


# Create a unique index for username
Index('subnetrange_index', SubnetRange.vrf_id, SubnetRange.range, unique=True)

# Index for cidr sorting
Index('subnetrange_order', SubnetRange.vrf_id, SubnetRange.range.family().desc(), SubnetRange.range.inet())


class Subnet(CommonMixin, Base):

    name = Column(String, nullable=False, default='')
    vrf_id = Column(Integer, ForeignKey("vrf.id"), nullable=False)
    vrf = relationship(Vrf)
    l3vni = Column(Integer, nullable=True)
    l2vni = Column(Integer, nullable=True)
    vlan = Column(Integer, nullable=True)
    subnet_ranges = relationship(
        "SubnetRange",
        lazy=False,
        order_by=(SubnetRange.vrf_id, SubnetRange.range.family().desc(), SubnetRange.range.inet()),
        cascade="all, delete-orphan",
    )
    ranges = association_proxy("subnet_ranges", "range")

    # Transient fields for ordering
    depth = None
    order = None

    @classmethod
    def _search_string(cls):
        return cls.name + " " + cls.notes

    def __str__(self):
        return "%s (%s)" % (', '.join(self.ranges), self.name)

    @hybrid_property
    def summary(self):
        return self.name

    @property
    def primary_range(self):
        return self.ranges and self.ranges[0]

    @classmethod
    def query_with_depth(cls):
        from ._dnszone import DnsZone

        query = Subnet.query.options(
            joinedload(Subnet.subnet_ranges),
            joinedload(Subnet.dnszones).options(
                defer('*'),
                undefer(DnsZone.id),
                undefer(DnsZone.name),
                raiseload(DnsZone.owner),
            ),
            joinedload(Subnet.vrf).options(
                defer('*'),
                undefer(Vrf.id),
                undefer(Vrf.name),
                raiseload(Vrf.owner),
            ),
        )
        subnets = query.all()

        # Update depth
        order = 0
        prev_subnet = []
        for subnet in subnets:
            while prev_subnet and (
                subnet.vrf_id != prev_subnet[-1].vrf_id
                or not subnet.subnet_ranges
                or subnet.subnet_ranges[0].version != prev_subnet[-1].subnet_ranges[0].version
                or not subnet.subnet_ranges[0].subnet_of(prev_subnet[-1].subnet_ranges[0])
            ):
                prev_subnet.pop()
            order = order + 1
            subnet.order = order
            subnet.depth = len(prev_subnet)
            if subnet.status != Subnet.STATUS_DELETED:
                prev_subnet.append(subnet)
        return subnets

    def to_json(self):
        data = super().to_json()
        if self.order is not None:
            data['order'] = self.order
        if self.depth is not None:
            data['depth'] = self.depth
        data['ranges'] = list(self.ranges)
        # Explicitly add primary_range
        data['primary_range'] = self.ranges[0] if self.ranges else None
        return data


@event.listens_for(Subnet, 'before_insert')
@event.listens_for(Subnet, 'before_update')
def receive_before_insert_or_update(mapper, connection, subnet):

    if not subnet.ranges:
        # you should probably use your own exception class here
        raise ValueError('ranges', _('at least one IPv6 or IPv4 network is required'))


# Create a unique index subnet & vrf
Index('subnet_vrf_index', Subnet.id, Subnet.vrf_id, unique=True)
