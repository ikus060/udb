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
from wtforms.fields import BooleanField, IntegerField, SelectField, StringField
from wtforms.fields.simple import TextAreaField
from wtforms.validators import DataRequired, Length

from udb.controller import flash, handle_exception, url_for, verify_perm
from udb.core.model import DnsRecord, User
from udb.tools.i18n import gettext as _

from .common_page import CommonPage
from .form import CherryForm, SelectObjectField


class EditDnsRecordForm(CherryForm):

    object_cls = DnsRecord

    name = StringField(
        _('Name'),
        validators=[
            DataRequired(),
            Length(max=256),
        ],
        render_kw={"placeholder": _("Enter a FQDN")},
    )

    type = SelectField(
        _('Type'),
        validators=[
            DataRequired(),
            Length(max=256),
        ],
        choices=list(zip(DnsRecord.TYPES, DnsRecord.TYPES)),
        default='A',
    )

    ttl = IntegerField(
        _('TTL'),
        validators=[DataRequired()],
        default='3600',
        render_kw={"placeholder": _("Time-to-live value (default: 3600)")},
    )

    value = StringField(
        _('Value'),
        validators=[
            DataRequired(),
            Length(max=256),
        ],
    )

    notes = TextAreaField(
        _('Notes'),
        default='',
        validators=[
            Length(max=256),
        ],
        render_kw={"placeholder": _("Enter details information about this subnet")},
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


class NewDnsRecordForm(EditDnsRecordForm):

    create_reverse_record = BooleanField(
        _('Create Reverse DNS Record'),
        render_kw={
            "data-showif-field": "type",
            "data-showif-operator": "in",
            "data-showif-value": '["A", "AAAA"]',
        },
    )

    create_forward_record = BooleanField(
        _('Create Forward DNS Record'),
        render_kw={
            "data-showif-field": "type",
            "data-showif-operator": "eq",
            "data-showif-value": 'PTR',
        },
    )

    def populate_obj(self, obj):
        """
        Special function to create reverse record if needed.
        """
        # Create DNS Record
        super().populate_obj(obj)

        # Then check if reverse should be created
        if self.create_reverse_record.data or self.create_forward_record.data:
            # Add record to trigger validation before creating the reverse record.
            obj.add()
            record = obj.create_reverse_dns_record(owner=obj.owner)
            if record:
                record.add()


class DnsRecordPage(CommonPage):
    def __init__(self):
        super().__init__(DnsRecord, EditDnsRecordForm, NewDnsRecordForm)

    @cherrypy.expose()
    def reverse_record(self, key, **kwargs):
        """
        Redirect user to reverse record or pre-fill a new form to create the record.
        """
        verify_perm(self.list_perm)
        # Return Not found if object doesn't exists
        obj = self._get_or_404(key)
        # If the reverse record doesn't exists, create it.
        reverse_record = obj.get_reverse_dns_record()
        if not reverse_record:
            verify_perm(self.new_perm)
            try:
                reverse_record = obj.create_reverse_dns_record(owner=cherrypy.serving.request.currentuser)
                if reverse_record:
                    reverse_record.add().commit()
                    flash(_("Reverse DNS Record created."))
                else:
                    flash(_("Cannnot create Reverse DNS Record."))
            except Exception as e:
                handle_exception(e)
        # Then redirect user
        if reverse_record:
            raise cherrypy.HTTPRedirect(url_for(reverse_record, 'edit'))
        else:
            raise cherrypy.HTTPRedirect(url_for(obj, 'edit'))

    def _list_query(self):
        """
        Drop unused fields
        """
        # Make use of short label to minimize footprint
        return DnsRecord.query.outerjoin(DnsRecord.owner).with_entities(
            DnsRecord.id,
            DnsRecord.status,
            DnsRecord.name,
            DnsRecord.type,
            DnsRecord.ttl,
            DnsRecord.value,
            DnsRecord.notes,
            User.summary.label('owner'),
        )
