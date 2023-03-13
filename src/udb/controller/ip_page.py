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
from sqlalchemy import func
from sqlalchemy.orm import defer, joinedload, undefer
from wtforms.fields import FieldList, FormField, IntegerField, StringField
from wtforms.fields.simple import TextAreaField
from wtforms.form import Form
from wtforms.validators import DataRequired, Length

from udb.core.model import DhcpRecord, DnsRecord, DnsZone, Ip, User
from udb.tools.i18n import gettext_lazy as _

from .common_page import CommonPage
from .form import CherryForm, SelectMultipleObjectField, SelectObjectField, SubnetTableWidget, TableWidget


class RelatedDnsRecordFrom(Form):

    name = StringField(_('Name'), render_kw={"readonly": True})
    type = StringField(_('Type'), render_kw={"readonly": True})
    ttl = IntegerField(_('TTL'), render_kw={"readonly": True})
    value = StringField(_('Value'), render_kw={"readonly": True})


class RelatedDhcpRecordForm(Form):

    mac = StringField(_('MAC'), render_kw={"readonly": True})


class RelatedSubnetForm(Form):

    name = StringField(_('Name'), render_kw={"readonly": True})
    ranges = StringField(
        _('IP Ranges'), render_kw={"readonly": True}, filters=[lambda ranges: ', '.join([str(r) for r in ranges])]
    )
    vrf = IntegerField(_('VRF'), render_kw={"readonly": True})
    dnszones = SelectMultipleObjectField(_('DNS zones'), object_cls=DnsZone.query)


class IpForm(CherryForm):
    """
    IP Form
    """

    object_cls = Ip

    ip = StringField(_('IP Address'), validators=[DataRequired()], render_kw={"readonly": True})

    related_dns_records = FieldList(
        FormField(RelatedDnsRecordFrom),
        label=_('Related DNS Records'),
        widget=TableWidget(),
    )

    related_dhcp_records = FieldList(
        FormField(RelatedDhcpRecordForm),
        label=_('Related DHCP Reservations'),
        widget=TableWidget(),
    )

    related_subnets = FieldList(
        FormField(RelatedSubnetForm),
        label=_('Supernets'),
        widget=SubnetTableWidget(),
    )

    notes = TextAreaField(
        _('Notes'),
        default='',
        validators=[Length(max=256)],
        render_kw={"placeholder": _("Enter details information about this IP Address"), "autofocus": True},
    )

    owner_id = SelectObjectField(
        _('Owner'),
        object_cls=User,
        object_query=lambda query: query.options(
            defer('*'),
            undefer('id'),
            undefer('fullname'),
            undefer('username'),
        ),
    )

    def populate_obj(self, obj):
        """
        Custom implementation to only update specific fields.
        """
        for field in ['owner_id', 'notes']:
            getattr(self, field).populate_obj(obj, field)


class IpPage(CommonPage):
    def __init__(self) -> None:
        super().__init__(Ip, IpForm, has_new=False)

    def _get_query(self, id):
        """
        Custom implementation to load related record.
        """
        return Ip.query.options(
            joinedload(Ip.related_dhcp_records),
            joinedload(Ip.related_dns_records),
        ).filter(Ip.id == id)

    def _list_query(self):
        """
        Custom implementation to load related record count.
        """
        return (
            Ip.query.outerjoin(Ip.owner)
            .outerjoin(Ip.related_dhcp_records)
            .outerjoin(Ip.related_dns_records)
            .group_by(Ip.id)
            .with_entities(
                Ip.id,
                Ip.ip,
                (func.count(DhcpRecord.id) + func.count(DnsRecord.id)).label('count'),
                Ip.notes,
                func.min(User.summary).label('owner'),
            )
        )
