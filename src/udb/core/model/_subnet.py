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
from sqlalchemy import Column, ForeignKey, Index, func
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import joinedload, relationship, validates
from sqlalchemy.types import Integer, String

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.tools.i18n import gettext_lazy as _

from ._cidr import CidrType
from ._common import CommonMixin
from ._vrf import Vrf

Base = cherrypy.tools.db.get_base()


class Subnet(CommonMixin, Base):

    name = Column(String, nullable=False, default='')
    ip_cidr = Column(CidrType, nullable=False)
    vrf_id = Column(Integer, ForeignKey("vrf.id"))
    vrf = relationship(Vrf)
    l3vni = Column(Integer, nullable=True)
    l2vni = Column(Integer, nullable=True)
    vlan = Column(Integer, nullable=True)
    depth = Column(Integer, nullable=False, server_default='0')

    @classmethod
    def _search_string(cls):
        return cls.name + " " + cls.notes + " " + cls.ip_cidr.text()

    @validates('ip_cidr')
    def validate_ip_cidr(self, key, value):
        try:
            return str(ipaddress.ip_network(value.strip(), strict=False))
        except ValueError:
            raise ValueError('ip_cidr', _('does not appear to be a valid IPv4 or IPv6 network'))

    @hybrid_property
    def related_supernets(self):
        return Subnet.query.filter(
            Subnet.status != Subnet.STATUS_DELETED,
            Subnet.vrf_id == self.vrf_id,
            Subnet.ip_cidr.supernet_of(self.ip_cidr),
        ).all()

    @hybrid_property
    def related_subnets(self):
        return Subnet.query.filter(
            Subnet.status != Subnet.STATUS_DELETED, Subnet.vrf_id == self.vrf_id, Subnet.ip_cidr.subnet_of(self.ip_cidr)
        ).all()

    def __str__(self):
        return "%s (%s)" % (self.ip_cidr, self.name)

    @hybrid_property
    def summary(self):
        return self.ip_cidr + " (" + self.name + ")"

    @property
    def ip_network(self):
        return ipaddress.ip_network(self.ip_cidr)

    @classmethod
    def query_with_depth(cls):
        from ._dnszone import DnsZone

        query = Subnet.query.options(
            joinedload(Subnet.owner),
            joinedload(Subnet.dnszones).raiseload(DnsZone.owner),
            joinedload(Subnet.vrf).raiseload(Vrf.owner),
        ).order_by(func.coalesce(Subnet.vrf_id, -1), Subnet.ip_cidr.inet())
        subnets = query.all()

        # Update depth
        prev_subnet = []
        for subnet in subnets:
            while prev_subnet and (
                subnet.vrf_id != prev_subnet[-1].vrf_id
                or subnet.ip_network.version != prev_subnet[-1].ip_network.version
                or not subnet.ip_network.subnet_of(prev_subnet[-1].ip_network)
            ):
                prev_subnet.pop()
            if subnet.depth != len(prev_subnet):
                subnet.depth = len(prev_subnet)
            if subnet.status != Subnet.STATUS_DELETED:
                prev_subnet.append(subnet)
        return subnets


# Make sure a subnet is unique within a vrf
Index('subnet_ip_cidr_vrf_unique_index', func.coalesce(Subnet.vrf_id, -1), Subnet.ip_cidr, unique=True)

# Index for cidr sorting
Index('subnet_ip_cidr_order', Subnet.vrf_id, Subnet.ip_cidr.inet())
