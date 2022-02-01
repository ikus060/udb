# -*- coding: utf-8 -*-
# udb, A web interface to manage IT network
# Copyright (C) 2021 IKUS Software inc.
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
import validators
from udb.controller import url_for
from udb.core.model import DhcpRecord, DnsRecord, DnsZone, Ip, Subnet, User
from udb.tools.i18n import gettext as _
from wtforms.fields import FieldList, FormField, IntegerField, StringField
from wtforms.fields import SelectField
from wtforms.fields.simple import TextAreaField
from wtforms.form import Form
from wtforms.validators import (DataRequired, IPAddress, MacAddress,
                                ValidationError)

from .form import (CherryForm, SelectMultiCheckbox, SelectMultipleObjectField,
                   SelectObjectField, TableWidget)


def validate_domain(form, field):
    if not validators.domain(field.data):
        raise ValidationError(_('Invalid FQDN'))


def validate_ip_cidr(form, field):
    if not validators.ipv4_cidr(field.data) and not validators.ipv6_cidr(field.data):
        raise ValidationError(_('Invalid subnet'))


class DnsZoneForm(CherryForm):

    object_cls = DnsZone

    @staticmethod
    def get_display_name():
        return _('DNS Zone')

    name = StringField(
        _('Name'),
        validators=[DataRequired(), validate_domain],
        render_kw={"placeholder": _("Enter a FQDN")})

    notes = TextAreaField(
        _('Notes'),
        default='',
        validators=[],
        render_kw={"placeholder": _("Enter details information about this DNS Zone")})

    owner = SelectObjectField(
        _('Owner'),
        object_cls=User,
        default=lambda: cherrypy.serving.request.currentuser.id)

    subnets = SelectMultipleObjectField(
        _('Allowed subnets'),
        object_cls=Subnet,
        widget=SelectMultiCheckbox())


class SubnetForm(CherryForm):

    object_cls = Subnet

    @staticmethod
    def get_display_name():
        return _('IP Subnet')

    ip_cidr = StringField(
        _('Subnet'),
        validators=[DataRequired(), validate_ip_cidr],
        render_kw={"placeholder": _("Enter a subnet IP/CIDR")})
    name = StringField(
        _('Name'),
        validators=[],
        render_kw={"placeholder": _("Enter a description")})
    vrf = IntegerField(
        _('VRF'),
        validators=[],
        render_kw={"placeholder": _("Enter a VRF number (optional)")})
    notes = TextAreaField(
        _('Notes'),
        default='',
        validators=[],
        render_kw={"placeholder": _("Enter details information about this subnet")})
    owner = SelectObjectField(
        _('Owner'),
        object_cls=User,
        default=lambda: cherrypy.serving.request.currentuser.id)
    dnszones = SelectMultipleObjectField(
        _('Allowed DNS zone'), object_cls=DnsZone, widget=SelectMultiCheckbox())


class DnsRecordForm(CherryForm):

    object_cls = DnsRecord

    @staticmethod
    def get_display_name():
        return _('DNS Record')

    name = StringField(
        _('Name'),
        validators=[DataRequired(), validate_domain],
        render_kw={"placeholder": _("Enter a FQDN")})

    type = SelectField(
        _('Type'),
        validators=[DataRequired()],
        choices=list(zip(DnsRecord.TYPES, DnsRecord.TYPES)))

    ttl = IntegerField(
        _('TTL'),
        validators=[DataRequired()],
        default='3600',
        render_kw={"placeholder": _("Time-to-live value (default: 3600)")})

    value = StringField(
        _('Value'),
        validators=[DataRequired()])

    notes = TextAreaField(
        _('Notes'),
        default='',
        validators=[],
        render_kw={"placeholder": _("Enter details information about this subnet")})

    owner = SelectObjectField(
        _('Owner'),
        object_cls=User,
        default=lambda: cherrypy.serving.request.currentuser.id)


class DhcpRecordForm(CherryForm):
    """
    DHCP Record Form
    """
    object_cls = DhcpRecord

    @staticmethod
    def get_display_name():
        return _('DHCP Record')

    ip = StringField(
        _('IP'),
        validators=[
            DataRequired(),
            IPAddress(ipv4=True, ipv6=True)],
        render_kw={"placeholder": _("Enter an IPv4 or IPv6 address")})

    mac = StringField(
        _('MAC'),
        validators=[
            DataRequired(),
            MacAddress()],
        render_kw={"placeholder": _("Enter a MAC address")})

    notes = TextAreaField(
        _('Notes'),
        default='',
        validators=[],
        render_kw={"placeholder": _("Enter details information about this DHCP Static Record")})

    owner = SelectObjectField(
        _('Owner'),
        object_cls=User,
        default=lambda: cherrypy.serving.request.currentuser.id)


class RelatedDnsRecordFrom(Form):

    name = StringField(
        _('Name'),
        render_kw={"readonly": True})

    type = StringField(
        _('Type'),
        render_kw={"readonly": True})

    ttl = IntegerField(
        _('TTL'),
        render_kw={"readonly": True})

    value = StringField(
        _('Value'),
        render_kw={"readonly": True})


class RelatedDhcpRecordForm(Form):

    mac = StringField(
        _('MAC'),
        render_kw={"readonly": True})


class IpForm(CherryForm):
    """
    IP Form
    """
    object_cls = Ip

    @ staticmethod
    def get_display_name():
        return _('IP Address')

    ip = StringField(
        _('IP Address'),
        validators=[DataRequired()],
        render_kw={"readonly": True})

    related_dns_records = FieldList(
        FormField(RelatedDnsRecordFrom),
        label=_('Related DNS Records'),
        widget=TableWidget(create_new_url=url_for(DnsRecord, 'new')))

    related_dhcp_records = FieldList(
        FormField(RelatedDhcpRecordForm),
        label=_('Related DHCP Records'),
        widget=TableWidget(create_new_url=url_for(DhcpRecord, 'new')))
