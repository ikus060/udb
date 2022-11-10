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
from sqlalchemy import or_, select, union
from sqlalchemy.ext.hybrid import hybrid_property

import udb.tools.db  # noqa: import cherrypy.tools.db

from ._dhcprecord import DhcpRecord
from ._dnsrecord import DnsRecord
from ._json import JsonMixin
from ._subnet import Subnet, SubnetRange

Base = cherrypy.tools.db.get_base()

# TODO Need to create index to make this query performant.

# Create a non-traditional mapping with multiple table.
# Read more about it here: https://docs.sqlalchemy.org/en/14/orm/nonstandard_mappings.html
# Create a query to list all existing IP address in various record type.
ip_entry = union(
    select(DhcpRecord.ip.label('ip')).filter(
        DhcpRecord.status != DhcpRecord.STATUS_DELETED,
    ),
    select(DnsRecord.value.label('ip')).filter(
        DnsRecord.type.in_(['A', 'AAAA']), DnsRecord.status != DnsRecord.STATUS_DELETED
    ),
    select(DnsRecord.reverse_ip.label('ip')).filter(
        DnsRecord.type == 'PTR',
        DnsRecord.status != DnsRecord.STATUS_DELETED,
    ),
).subquery()


class Ip(JsonMixin, Base):
    """
    This ORM is a view on all IP address declared in various record type.
    """

    __table__ = ip_entry
    __mapper_args__ = {'primary_key': [ip_entry.c.ip]}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @hybrid_property
    def summary(self):
        return self.ip

    @property
    def related_dns_records(self):
        """
        Return list of related DNS record. That include all DNS record with FQDN matching our current IP address and reverse pointer (PTR).
        """
        return DnsRecord.query.filter(
            DnsRecord.status != DnsRecord.STATUS_DELETED,
            or_(
                DnsRecord.name.in_(select(DnsRecord.name).filter(DnsRecord.value == self.ip)),
                DnsRecord.name == ipaddress.ip_address(self.ip).reverse_pointer,
            ),
        ).all()

    @property
    def related_dhcp_records(self):
        return DhcpRecord.query.filter(
            DhcpRecord.status != DhcpRecord.STATUS_DELETED,
            DhcpRecord.ip == self.ip,
        ).all()

    @property
    def related_subnets(self):
        return (
            Subnet.query.join(Subnet.subnet_ranges)
            .filter(
                SubnetRange.range.supernet_of(self.ip),
                Subnet.status != Subnet.STATUS_DELETED,
            )
            .all()
        )
