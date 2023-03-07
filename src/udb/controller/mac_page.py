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
from sqlalchemy.orm import defer, undefer
from wtforms.fields import FieldList, FormField, StringField
from wtforms.fields.simple import TextAreaField
from wtforms.form import Form
from wtforms.validators import DataRequired, Length

from udb.core.model import DhcpRecord, Mac, User
from udb.tools.i18n import gettext_lazy as _

from .common_page import CommonPage
from .form import CherryForm, SelectObjectField, TableWidget


class RelatedDhcpRecordForm(Form):

    ip = StringField(_('IP'), render_kw={"readonly": True})


class MacForm(CherryForm):
    """
    Mac Form
    """

    object_cls = Mac

    mac = StringField(_('MAC Address'), validators=[DataRequired()], render_kw={"readonly": True})

    related_dhcp_records = FieldList(
        FormField(RelatedDhcpRecordForm),
        label=_('Related DHCP Reservations'),
        widget=TableWidget(),
    )

    notes = TextAreaField(
        _('Notes'),
        default='',
        validators=[Length(max=256)],
        render_kw={"placeholder": _("Enter details information about this MAC Address")},
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


class MacPage(CommonPage):
    def __init__(self) -> None:
        super().__init__(Mac, MacForm, has_new=False)

    def _list_query(self):
        return (
            Mac.query.outerjoin(Mac.owner)
            .outerjoin(Mac.related_dhcp_records)
            .group_by(Mac.id)
            .with_entities(
                Mac.id,
                Mac.mac,
                func.count(DhcpRecord.id).label('count'),
                Mac.notes,
                func.min(User.summary).label('owner'),
            )
        )

    def _to_json(self, obj):
        return super()._to_json(obj)
