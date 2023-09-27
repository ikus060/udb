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

import cherrypy
from sqlalchemy import case, func
from wtforms.fields import StringField
from wtforms.fields.simple import TextAreaField
from wtforms.validators import DataRequired, Length

from udb.core.model import DnsRecord, DnsZone, Subnet, SubnetRange, User
from udb.tools.i18n import gettext_lazy as _

from .common_page import CommonPage
from .form import CherryForm, DualListWidget, SelectMultipleObjectField, SelectObjectField


def _subnet_query(query):
    """
    Adjust the original query to list the subnet name and subnet ranges.
    """
    return (
        query.with_entities(
            Subnet.id,
            (func.group_concat(SubnetRange.range.text(), order_by=SubnetRange.range.desc()) + " " + Subnet.name).label(
                'summary'
            ),
            Subnet.estatus,
        )
        .join(Subnet.subnet_ranges)
        .group_by(Subnet.id)
        .order_by(
            func.min(case((SubnetRange.version == 6, SubnetRange.range), else_=None)),
            func.min(case((SubnetRange.version == 4, SubnetRange.range), else_=None)),
        )
    )


class DnsZoneForm(CherryForm):

    object_cls = DnsZone

    name = StringField(
        _('Name'),
        validators=[
            DataRequired(),
            Length(max=256),
        ],
        render_kw={"placeholder": _("Enter a FQDN"), "autofocus": True},
    )

    subnets = SelectMultipleObjectField(
        _('Allowed subnets'),
        object_cls=Subnet,
        # Completly replace the query to include the subnet ranges in the summary
        object_query=_subnet_query,
        widget=DualListWidget(),
    )

    notes = TextAreaField(
        _('Notes'),
        default='',
        validators=[Length(max=256)],
        render_kw={"placeholder": _("Enter details information about this DNS Zone")},
    )

    owner_id = SelectObjectField(
        _('Owner'),
        object_cls=User,
        default=lambda: cherrypy.serving.request.currentuser.id,
    )


class DnsZonePage(CommonPage):
    def __init__(self):
        super().__init__(DnsZone, DnsZoneForm, new_perm=User.PERM_DNSZONE_CREATE)

    def _list_query(self):
        return (
            DnsZone.query.outerjoin(DnsZone.owner)
            .outerjoin(DnsZone.subnets)
            .with_entities(
                DnsZone.id,
                DnsZone.estatus,
                DnsZone.name,
                func.count(Subnet.id),
                DnsZone.notes,
                User.summary.label('owner'),
            )
            .group_by(DnsZone.id, User.summary)
        )

    @cherrypy.expose()
    @cherrypy.tools.jinja2(template=['dnszone/zone.j2'])
    @cherrypy.tools.response_headers(headers=[('Content-Type', 'text/plain')])
    def zonefile(self, key, **kwargs):
        """
        Generate a DNS Zone file.
        """
        zone = self._get_or_404(key)
        # Get list of dns record included in this zone.
        # Make sure SOA is first
        dnsrecords = (
            DnsRecord.query.with_entities(
                DnsRecord.id,
                DnsRecord.name,
                DnsRecord.type,
                DnsRecord.ttl,
                DnsRecord.value,
            )
            .filter(DnsRecord.estatus == DnsRecord.STATUS_ENABLED, DnsRecord.dnszone_id == zone.id)
            .all()
        )
        return {'dnsrecords': [r._asdict() for r in dnsrecords], 'dnsrecord_sort_key': DnsRecord.dnsrecord_sort_key}
