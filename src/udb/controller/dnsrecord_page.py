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
from wtforms.fields import BooleanField, IntegerField, SelectField, StringField
from wtforms.fields.simple import TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange

from udb.controller import flash, show_exception, url_for, verify_perm
from udb.core.model import DnsRecord, User, Vrf
from udb.tools.i18n import gettext_lazy as _

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
        render_kw={"placeholder": _("Enter a FQDN"), "autofocus": True},
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
        validators=[DataRequired(), NumberRange(min=1, max=2147483647, message=_('TTL must be at least %(min)s.'))],
        default=3600,
        render_kw={
            "placeholder": _("Time-to-live value (default: 3600)"),
            "pattern": "\\d+",
            "title": _('Time to live in seconds.'),
        },
    )

    value = StringField(
        _('Value'),
        validators=[
            DataRequired(),
            Length(max=256),
        ],
    )

    vrf_id = SelectObjectField(
        _('VRF'),
        object_cls=Vrf,
        description=_("Determined automatically if left blank."),
        render_kw={
            "data-showif-field": "type",
            "data-showif-operator": "in",
            "data-showif-value": '["A", "AAAA", "PTR"]',
        },
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
                reverse_record.add().commit()
                flash(_("Reverse DNS Record created."))
            except Exception as e:
                cherrypy.tools.db.get_session().rollback()
                flash(_("Cannnot create Reverse DNS Record."), level='error')
                show_exception(e, obj=reverse_record)
                reverse_record = None
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
        return (
            DnsRecord.query.outerjoin(DnsRecord.owner)
            .outerjoin(DnsRecord.vrf)
            .with_entities(
                DnsRecord.id,
                DnsRecord.estatus,
                DnsRecord.name,
                DnsRecord.type,
                DnsRecord.ttl,
                DnsRecord.value,
                Vrf.id,
                Vrf.name,
                DnsRecord.notes,
                User.summary.label('owner'),
            )
        )

    @cherrypy.expose
    @cherrypy.tools.jinja2(template=['{model_name}/list.html', 'common/list.html'])
    def index(self):
        """
        This implementation return a list of VRF
        """
        values = super().index()
        # Query VRF with number of assigned Dns Record.
        values['vrf_list'] = [
            (row.id, row.name, row.count)
            for row in Vrf.query.with_entities(Vrf.id, Vrf.name, func.count(DnsRecord.id).label('count'))
            .outerjoin(DnsRecord)
            .group_by(Vrf.id)
            .all()
        ]
        return values

    @cherrypy.expose()
    @cherrypy.tools.json_out()
    def related(self, key, **kwargs):
        obj = self._get_or_404(key)
        query = obj.related_dns_record_query().with_entities(
            DnsRecord.id,
            DnsRecord.estatus,
            DnsRecord.name,
            DnsRecord.type,
            DnsRecord.ttl,
            DnsRecord.value,
        )
        return {'data': [list(row) + [url_for('dnsrecord', row[0], 'edit')] for row in query.all()]}
