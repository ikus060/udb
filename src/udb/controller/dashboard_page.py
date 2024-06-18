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
from datetime import datetime, timedelta, timezone

import cherrypy
from sqlalchemy import desc, func

from udb.core.model import DhcpRecord, DnsRecord, DnsZone, Ip, Mac, Message, Subnet, User, Vrf

Base = cherrypy.tools.db.get_base()


class DashboardPage:
    @cherrypy.expose()
    @cherrypy.tools.jinja2(template=['dashboard.html'])
    def index(self, **kwargs):
        # Most active users
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        user_activities = (
            Message.query.with_entities(User, func.count(Message.author_id).label('count'))
            .filter(Message.author_id.is_not(None), Message.date >= week_ago)
            .group_by(User)
            .order_by(desc('count'))
            .join(User)
            .limit(10)
            .all()
        )

        # Count records
        vrf_count = Vrf.query.filter(Vrf.estatus != Vrf.STATUS_DELETED).count()
        subnet_count = Subnet.query.filter(Subnet.estatus != Subnet.STATUS_DELETED).count()
        dnszone_count = DnsZone.query.filter(DnsZone.estatus != DnsZone.STATUS_DELETED).count()
        dnsrecord_count = DnsRecord.query.filter(DnsRecord.estatus != DnsRecord.STATUS_DELETED).count()
        dhcprecord_count = DhcpRecord.query.filter(DhcpRecord.estatus != DhcpRecord.STATUS_DELETED).count()
        mac_count = Mac.query.count()
        ip_count = Ip.query.count()
        return {
            'vrf_count': vrf_count,
            'dnszone_count': dnszone_count,
            'ip_count': ip_count,
            'subnet_count': subnet_count,
            'dnsrecord_count': dnsrecord_count,
            'dhcprecord_count': dhcprecord_count,
            'mac_count': mac_count,
            'user_activities': user_activities,
        }
