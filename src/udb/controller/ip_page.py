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

from wtforms.fields import FieldList, FormField, IntegerField, StringField
from wtforms.form import Form
from wtforms.validators import DataRequired

from udb.core.model import DnsZone, Ip
from udb.tools.i18n import gettext as _

from .common_page import CommonPage
from .form import CherryForm, SelectMultipleObjectField, SubnetTableWidget, TableWidget


class RelatedDnsRecordFrom(Form):

    name = StringField(_('Name'), render_kw={"readonly": True})
    type = StringField(_('Type'), render_kw={"readonly": True})
    ttl = IntegerField(_('TTL'), render_kw={"readonly": True})
    value = StringField(_('Value'), render_kw={"readonly": True})


class RelatedDhcpRecordForm(Form):

    mac = StringField(_('MAC'), render_kw={"readonly": True})


class RelatedSubnetForm(Form):

    ip_cidr = StringField(_('Subnet'), render_kw={"readonly": True})
    name = StringField(_('Name'), render_kw={"readonly": True})
    vrf = IntegerField(_('VRF'), render_kw={"readonly": True})
    dnszones = SelectMultipleObjectField(_('DNS zones'), object_cls=DnsZone)


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
        label=_('Related DHCP Records'),
        widget=TableWidget(),
    )

    related_subnets = FieldList(
        FormField(RelatedSubnetForm),
        label=_('Supernets'),
        widget=SubnetTableWidget(),
    )


class IpPage(CommonPage):
    def __init__(self) -> None:
        super().__init__(Ip, IpForm, has_new=False)
