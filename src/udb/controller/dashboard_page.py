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
from datetime import datetime, timedelta

import cherrypy
from sqlalchemy import desc, func

from udb.controller import lastupdated, url_for
from udb.core.model import DhcpRecord, DnsRecord, DnsZone, Ip, Message, Subnet, User, Vrf

Base = cherrypy.tools.db.get_base()


class DashboardPage:
    @cherrypy.expose()
    @cherrypy.tools.jinja2(template=['dashboard.html'])
    def index(self, **kwargs):
        # Most active user
        week_ago = datetime.now() - timedelta(days=7)
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
        vrf_count = Vrf.query.filter(Vrf.status == Vrf.STATUS_ENABLED).count()
        subnet_count = Subnet.query.filter(Subnet.status == Subnet.STATUS_ENABLED).count()
        dnszone_count = DnsZone.query.filter(DnsZone.status == DnsZone.STATUS_ENABLED).count()
        dnsrecord_count = DnsRecord.query.filter(DnsRecord.status == DnsRecord.STATUS_ENABLED).count()
        dhcprecord_count = DhcpRecord.query.filter(DhcpRecord.status == DhcpRecord.STATUS_ENABLED).count()
        ip_count = Ip.query.count()
        return {
            'vrf_count': vrf_count,
            'dnszone_count': dnszone_count,
            'ip_count': ip_count,
            'subnet_count': subnet_count,
            'dnsrecord_count': dnsrecord_count,
            'dhcprecord_count': dhcprecord_count,
            'user_activities': user_activities,
        }

    @cherrypy.expose()
    @cherrypy.tools.json_out()
    def activities_json(self, **kwargs):
        # List all activities by dates
        obj_list = (
            Message.query.filter(Message.type.in_([Message.TYPE_NEW, Message.TYPE_DIRTY]))
            .order_by(Message.date.desc())
            .limit(10)
            .all()
        )
        return {
            'data': [
                dict(
                    obj.to_json(),
                    **{
                        'url': url_for(obj.model_object, 'edit'),
                        'summary': obj.summary,
                        'author_name': obj.author_name,
                        'date_lastupdated': lastupdated(obj.date),
                    }
                )
                for obj in obj_list
            ]
        }
