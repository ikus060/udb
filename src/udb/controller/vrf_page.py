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
from sqlalchemy.orm import defer, undefer
from wtforms.fields import StringField
from wtforms.fields.simple import TextAreaField
from wtforms.validators import DataRequired, Length

from udb.core.model import User, Vrf
from udb.tools.i18n import gettext_lazy as _

from .common_page import CommonPage
from .form import CherryForm, SelectObjectField


class VrfForm(CherryForm):
    object_cls = Vrf

    name = StringField(
        _('Name'), validators=[DataRequired(), Length(max=256)], render_kw={"placeholder": _("Enter a VRF name")}
    )

    notes = TextAreaField(
        _('Notes'),
        default='',
        validators=[Length(max=256)],
        render_kw={"placeholder": _("Enter details information about this VRF")},
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
        default=lambda: cherrypy.serving.request.currentuser.id,
    )


class VrfPage(CommonPage):
    def __init__(self):
        super().__init__(Vrf, VrfForm)

    def _list_query(self):
        return Vrf.session.query(
            Vrf.id,
            Vrf.status,
            Vrf.name,
            Vrf.notes,
            User.summary.label('owner'),
        ).outerjoin(Vrf.owner)
