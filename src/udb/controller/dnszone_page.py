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
from sqlalchemy.orm import joinedload
from wtforms.fields import StringField
from wtforms.fields.simple import TextAreaField
from wtforms.validators import DataRequired

from udb.core.model import DnsZone, Subnet, User
from udb.tools.i18n import gettext as _

from .common_page import CommonPage
from .form import CherryForm, SelectMultiCheckbox, SelectMultipleObjectField, SelectObjectField


class DnsZoneForm(CherryForm):

    object_cls = DnsZone

    name = StringField(_('Name'), validators=[DataRequired()], render_kw={"placeholder": _("Enter a FQDN")})

    notes = TextAreaField(
        _('Notes'),
        default='',
        validators=[],
        render_kw={"placeholder": _("Enter details information about this DNS Zone")},
    )

    owner = SelectObjectField(_('Owner'), object_cls=User, default=lambda: cherrypy.serving.request.currentuser.id)

    subnets = SelectMultipleObjectField(_('Allowed subnets'), object_cls=Subnet, widget=SelectMultiCheckbox())


class DnsZonePage(CommonPage):
    def __init__(self):
        super().__init__(DnsZone, object_form=DnsZoneForm)

    def _query(self):
        return DnsZone.query.options(joinedload(DnsZone.owner), joinedload(DnsZone.subnets))
