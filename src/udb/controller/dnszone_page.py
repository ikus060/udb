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
from sqlalchemy import func
from sqlalchemy.orm import aliased
from wtforms.fields import StringField
from wtforms.fields.simple import TextAreaField
from wtforms.validators import DataRequired, Length

from udb.core.model import DnsRecord, DnsZone, Subnet, User
from udb.tools.i18n import gettext_lazy as _

from .common_page import CommonPage
from .form import CherryForm, SelectMultipleObjectField, SelectObjectField


def _subnet_query():
    """
    Adjust the original query to list the subnet name and subnet ranges and Hide slave subnets.
    """
    return (
        Subnet.query.with_entities(
            Subnet.id,
            (func.group_concat(Subnet.range.text(), order_by=Subnet.range.desc()) + " " + Subnet.name).label('summary'),
            Subnet.estatus,
        )
        .filter(Subnet.slave.is_(False))
        .group_by(Subnet.id)
        .order_by(func.family(Subnet.range).desc(), Subnet.range)
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
        render_kw={
            "class": "multi",
            "data-non_selected_header": _("Available"),
            "data-selected_header": _("Selected"),
            "data-search_placeholder": _("Filter..."),
        },
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

    def populate_obj(self, obj):
        self.name.populate_obj(obj, 'name')
        self.notes.populate_obj(obj, 'notes')
        self.owner_id.populate_obj(obj, 'owner_id')

        # To update subnets, we ignore slaves.
        obj_subnets = list([s for s in obj.subnets if not s.slave])
        for subnet_id in self.subnets.data:
            match = [s for s in obj_subnets if s.id == subnet_id]
            if match:
                obj_subnets.remove(match[0])
            else:
                # Add master subnet
                new_subnet = Subnet.query.filter(Subnet.id == subnet_id).first()
                obj.subnets.append(new_subnet)
        for not_found in obj_subnets:
            if not not_found.slave:
                obj.subnets.remove(not_found)


class DnsZonePage(CommonPage):
    def __init__(self):
        super().__init__(DnsZone, DnsZoneForm, new_perm=User.PERM_DNSZONE_CREATE)

    def _list_query(self):
        a1 = aliased(DnsZone)
        subnet_count = (
            Subnet.query.with_entities(func.count(Subnet.id))
            .join(a1.subnets)
            .filter(a1.id == DnsZone.id, Subnet.slave.is_(False), Subnet.estatus != Subnet.STATUS_DELETED)
            .scalar_subquery()
        )
        dnsrecord_count = (
            DnsRecord.query.with_entities(func.count(DnsRecord.id))
            .filter(DnsRecord.dnszone_id == DnsZone.id, DnsRecord.estatus != DnsRecord.STATUS_DELETED)
            .scalar_subquery()
        )
        return DnsZone.query.outerjoin(DnsZone.owner).with_entities(
            DnsZone.id,
            DnsZone.estatus,
            DnsZone.name,
            subnet_count,
            dnsrecord_count,
            DnsZone.notes,
            User.summary.label('owner'),
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
