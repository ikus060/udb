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
from wtforms.fields import Field, IntegerField, StringField
from wtforms.fields.simple import TextAreaField
from wtforms.validators import DataRequired, Length, Optional, StopValidation, ValidationError
from wtforms.widgets import TextInput

from udb.core.model import DnsZone, Subnet, User, Vrf
from udb.tools.i18n import gettext as _

from . import url_for
from .common_page import CommonPage
from .form import CherryForm, SelectMultiCheckbox, SelectMultipleObjectField, SelectObjectField, StringFieldSetWidget

unset_value = "UNSET_DATA"


class StringFieldSet(Field):

    widget = StringFieldSetWidget()

    inner_widget = TextInput()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, default=[], **kwargs)

    def process_formdata(self, valuelist):
        if valuelist:
            self.data = [v for v in set(valuelist) if v.strip()]

    def _run_validation_chain(self, form, validators):
        """
        Run a validation chain, stopping if any validator raises StopValidation.

        :param form: The Form instance this field belongs to.
        :param validators: a sequence or iterable of validator callables.
        :return: True if validation was stopped, False otherwise.
        """
        f = StringField()
        for value in self.data:
            f.data = value
            for validator in validators:
                try:
                    validator(form, f)
                except StopValidation as e:
                    if e.args and e.args[0]:
                        self.errors.append(e.args[0])
                    return True
                except ValidationError as e:
                    self.errors.append(e.args[0])
        return False

    def populate_obj(self, obj, name):
        proxy = getattr(obj, name)
        if hasattr(proxy, 'append'):
            for value in self.data:
                if value not in proxy:
                    proxy.append(value)
            for value in list(proxy):
                if value not in self.data:
                    proxy.remove(value)
        else:
            setattr(obj, name, self.data)


class SubnetForm(CherryForm):

    object_cls = Subnet
    name = StringField(_('Name'), validators=[Length(max=256)], render_kw={"placeholder": _("Enter a description")})
    notes = TextAreaField(
        _('Notes'),
        default='',
        validators=[Length(max=256)],
        render_kw={"placeholder": _("Enter details information about this subnet")},
    )
    ranges = StringFieldSet(
        label=_('IP Ranges'),
        validators=[Length(max=256)],
        render_kw={"placeholder": _("Enter IPv4 or IPv6 address")},
    )
    vrf_id = SelectObjectField(
        _('VRF'),
        object_cls=Vrf,
        object_query=lambda query: query.options(
            defer('*'),
            undefer('id'),
            undefer('name'),
        ),
        validators=[DataRequired()],
        render_kw={"placeholder": _("Enter a VRF number (optional)")},
    )
    l3vni = IntegerField(_('L3VNI'), validators=[Optional()], render_kw={'width': '1/3'})
    l2vni = IntegerField(_('L2VNI'), validators=[Optional()], render_kw={'width': '1/3'})
    vlan = IntegerField(_('VLAN'), validators=[Optional()], render_kw={'width': '1/3'})
    dnszones = SelectMultipleObjectField(
        _('Allowed DNS zone(s)'),
        object_cls=DnsZone,
        object_query=lambda query: query.options(
            defer('*'),
            undefer('id'),
            undefer('name'),
        ),
        widget=SelectMultiCheckbox(),
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
