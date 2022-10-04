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
from wtforms.fields import IntegerField, StringField
from wtforms.fields.simple import TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from udb.core.model import DnsZone, Subnet, User, Vrf
from udb.tools.i18n import gettext as _

from . import url_for
from .common_page import CommonPage
from .form import CherryForm, SelectMultiCheckbox, SelectMultipleObjectField, SelectObjectField


class SubnetForm(CherryForm):

    object_cls = Subnet

    ip_cidr = StringField(
        _('Subnet'),
        validators=[DataRequired(), Length(max=256)],
        render_kw={"placeholder": _("Enter a subnet IP/CIDR")},
    )
    name = StringField(_('Name'), validators=[Length(max=256)], render_kw={"placeholder": _("Enter a description")})
    vrf = SelectObjectField(
        _('VRF'), object_cls=Vrf, validators=[Optional()], render_kw={"placeholder": _("Enter a VRF number (optional)")}
    )
    l3vni = IntegerField(_('L3VNI'), validators=[Optional()])
    l2vni = IntegerField(_('L2VNI'), validators=[Optional()])
    vlan = IntegerField(_('VLAN'), validators=[Optional()])
    dnszones = SelectMultipleObjectField(_('Allowed DNS zone(s)'), object_cls=DnsZone, widget=SelectMultiCheckbox())
    notes = TextAreaField(
        _('Notes'),
        default='',
        validators=[Length(max=256)],
        render_kw={"placeholder": _("Enter details information about this subnet")},
    )
    owner = SelectObjectField(_('Owner'), object_cls=User, default=lambda: cherrypy.serving.request.currentuser.id)


class SubnetPage(CommonPage):
    def __init__(self):
        super().__init__(Subnet, object_form=SubnetForm)

    def _query(self):
        return Subnet.query_with_depth()

    def _to_json(self, subnet):
        data = subnet.to_json()
        data.update(
            {
                'vrf_name': subnet.vrf.name,
                'dnszones': [obj.name for obj in subnet.dnszones],
                'url': url_for(subnet, 'edit'),
            }
        )
        return data
