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
from sqlalchemy import Column, ForeignKey, Index, Integer, event, func, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import column_property, declared_attr, relationship, validates

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.tools.i18n import gettext_lazy as _

from ._cidr import InetType
from ._common import CommonMixin
from ._dhcprecord import DhcpRecord
from ._dnsrecord import DnsRecord
from ._follower import FollowerMixin
from ._json import JsonMixin
from ._message import MessageMixin
from ._search_string import SearchableMixing
from ._subnet import Subnet, SubnetRange
from ._vrf import Vrf

Base = cherrypy.tools.db.get_base()

Session = cherrypy.tools.db.get_session()


class Ip(CommonMixin, JsonMixin, MessageMixin, FollowerMixin, SearchableMixing, Base):
    __tablename__ = 'ip'
    ip = Column(InetType, nullable=False)
    vrf_id = Column(Integer, ForeignKey("vrf.id"), nullable=False)
    vrf = relationship(Vrf)
    related_dhcp_records = relationship(DhcpRecord, back_populates="_ip", lazy=True)
    related_dns_records = relationship(
        DnsRecord, back_populates="_ip", lazy=True, foreign_keys="[DnsRecord.generated_ip]"
    )

    @classmethod
    def _search_string(cls):
        return cls.ip.host() + " " + cls.notes

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
        return (
            Subnet.query.join(Subnet.subnet_ranges)
            .filter(
                SubnetRange.version == func.family(self.ip),
                SubnetRange.start_ip <= self.ip,
                SubnetRange.end_ip > self.ip,
                Subnet.vrf_id == self.vrf_id,
                Subnet.status != Subnet.STATUS_DELETED,
            )
            .all()
        )

    @declared_attr
    def related_dhcp_records_count(cls):
        return column_property(
            select(func.count(DhcpRecord.id))
            .where(
                DhcpRecord.ip == cls.ip,
                DhcpRecord.vrf_id == cls.vrf_id,
                DhcpRecord.status != DhcpRecord.STATUS_DELETED,
            )
            .scalar_subquery(),
            deferred=True,
        )

    @declared_attr
    def related_dns_records_count(cls):
        return column_property(
            select(func.count(DnsRecord.id))
            .where(
                DnsRecord.generated_ip == cls.ip,
                DnsRecord.vrf_id == cls.vrf_id,
                DnsRecord.status != DnsRecord.STATUS_DELETED,
            )
            .scalar_subquery(),
            deferred=True,
        )

    @property
    def referenced(self):
        return self.related_dhcp_records_count > 0 or self.related_dns_records_count > 0

    @property
    def reverse_pointer(self):
        """
        Return the reverse PTR value of this IP.
        """
        return ipaddress.ip_address(self.ip).reverse_pointer


Index('vrf_ip_unique_index', Ip.vrf_id, Ip.ip, unique=True)


@event.listens_for(Session, "before_flush", insert=True)
def _update_ip(session, flush_context, instances):
    """
    Create missing IP Record when creating or updating record.
    """
    # First pass to make sure IP Record are unique
    for instance in itertools.chain(session.new, session.dirty):
        if hasattr(instance, '_ip_column_name'):
            # Get IP Value and VRF
            try:
                ip_value = getattr(instance, instance._ip_column_name)
                ip_value = ipaddress.ip_address(ip_value).exploded
                if getattr(instance, 'vrf'):
                    vrf_id = instance.vrf.id
                else:
                    vrf_id = getattr(instance, 'vrf_id')
            except ValueError:
                ip_value = None
                vrf_id = None
            # Make sure to get/create unique IP record.
            # Do not assign the object as it might impact the update statement for generated column.
            if ip_value is not None and vrf_id is not None:
                instance._ip  # Fetch the Ip for history
                instance._ip = _unique_ip(session, ip_value, vrf_id)


def _unique_ip(session, ip_value, vrf_id):
    """
    Using a session cache, make sure to return unique IP object.
    """
    assert ip_value and vrf_id
    cache = getattr(session, '_unique_ip_cache', None)
    if cache is None:
        session._unique_ip_cache = cache = {}

    if ip_value in cache:
        return cache[ip_value]
    else:
        with session.no_autoflush:
            obj = session.query(Ip).filter_by(ip=ip_value, vrf_id=vrf_id).first()
            if not obj:
                obj = Ip(ip=ip_value, vrf_id=vrf_id)
                session.add(obj)
        cache[ip_value] = obj
        return obj
