# udb, A web interface to manage IT network
# Copyright (C) 2022-2026 IKUS Software inc.
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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import ipaddress

import cherrypy
from cherrypy_foundation.tools.i18n import gettext_lazy as _
from sqlalchemy import Column, ForeignKey, Index, Integer, func
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, validates

from ._cidr import InetType
from ._common import CommonMixin
from ._follower import FollowerMixin
from ._json import JsonMixin
from ._message import MessageMixin
from ._search_string import SearchableMixing
from ._subnet import Subnet
from ._vrf import Vrf

Base = cherrypy.db.base


class Ip(CommonMixin, JsonMixin, MessageMixin, FollowerMixin, SearchableMixing, Base):
    __tablename__ = 'ip'
    ip = Column(InetType, nullable=False)
    vrf_id = Column(Integer, ForeignKey("vrf.id"), nullable=False)
    vrf = relationship(Vrf)
    related_dhcp_records = relationship("DhcpRecord", back_populates="_ip", lazy=True, overlaps="vrf")
    related_dns_records = relationship("DnsRecord", back_populates="_ip", lazy=True, overlaps="vrf,_subnet")

    @classmethod
    def _search_string(cls):
        return cls.ip.host() + " " + cls.notes

    @classmethod
    def unique_ip(cls, ip_value, vrf):
        """
        Using a session cache, make sure to return unique IP object.
        """
        assert ip_value and vrf
        session = cherrypy.db.session
        # Search current sessions for matching IP
        matching_ip = next(
            (obj for obj in session.new if isinstance(obj, Ip) and obj.ip == ip_value and obj.vrf == vrf), None
        )
        if matching_ip:
            return matching_ip
        # If not found in our session, search database.
        obj = Ip.query.filter_by(ip=ip_value, vrf_id=vrf.id).first()
        if obj:
            return obj
        # If not found in database, create it.
        return Ip(ip=ip_value, vrf=vrf).add()

    @hybrid_property
    def summary(self):
        return self.ip

    @summary.expression
    def summary(self):
        return self.ip.host()

    @validates('ip')
    def validate_ip(self, key, value):
        # Validated at application level to avoid Postgresql raising exception
        try:
            ipaddress.ip_address(value)
        except ValueError:
            raise ValueError('ip', _('expected a valid ipv4 or ipv6'))
        return value

    @property
    def related_subnets(self):
        return Subnet.query.filter(
            func.subnet_of(self.ip, Subnet.range),
            Subnet.vrf_id == self.vrf_id,
            Subnet.estatus != Subnet.STATUS_DELETED,
        ).all()

    @property
    def reverse_pointer(self):
        """
        Return the reverse PTR value of this IP.
        """
        return ipaddress.ip_address(self.ip).reverse_pointer


Index(
    'ip_vrf_id_ip_unique_ix',
    Ip.vrf_id,
    Ip.ip,
    unique=True,
    info={
        'description': _('An IP address must be unique within a VRF.'),
    },
)
