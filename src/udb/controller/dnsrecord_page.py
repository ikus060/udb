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
from wtforms.fields import IntegerField, SelectField, StringField
from wtforms.fields.simple import TextAreaField
from wtforms.validators import DataRequired

from udb.core.model import DnsRecord, User
from udb.tools.i18n import gettext as _

from .common_page import CommonPage
from .form import CherryForm, SelectObjectField


class DnsRecordForm(CherryForm):

    object_cls = DnsRecord

    name = StringField(_('Name'), validators=[DataRequired()], render_kw={"placeholder": _("Enter a FQDN")})

    type = SelectField(_('Type'), validators=[DataRequired()], choices=list(zip(DnsRecord.TYPES, DnsRecord.TYPES)))

    ttl = IntegerField(
        _('TTL'),
        validators=[DataRequired()],
        default='3600',
        render_kw={"placeholder": _("Time-to-live value (default: 3600)")},
    )

    value = StringField(_('Value'), validators=[DataRequired()])

    owner = SelectObjectField(_('Owner'), object_cls=User, default=lambda: cherrypy.serving.request.currentuser.id)

    notes = TextAreaField(
        _('Notes'),
        default='',
        validators=[],
        render_kw={"placeholder": _("Enter details information about this subnet")},
    )


class DnsRecordPage(CommonPage):
    def __init__(self):
        super().__init__(DnsRecord, DnsRecordForm)
