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
from udb.controller.common import CommonApi, CommonPage
from udb.core.model import DhcpRecord, DnsRecord, DnsZone, Subnet
from udb.tools.i18n import gettext as _
from wtforms.fields import IntegerField, StringField
from wtforms.fields.simple import TextAreaField
from wtforms.validators import (
    DataRequired, IPAddress, MacAddress, ValidationError)

from .fields import DnsRecordType, UserField
from .wtf import CherryForm


def validate_domain(form, field):
    if not validators.domain(field.data):
        raise ValidationError(_('Invalid FQDN'))


def validate_ip_cidr(form, field):
    if not validators.ipv4_cidr(field.data) and not validators.ipv6_cidr(field.data):
        raise ValidationError(_('Invalid subnet'))

#
# DNS Zone
#


class DnsZoneForm(CherryForm):

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
    owner = UserField(
        _('Owner'),
        default=lambda: cherrypy.serving.request.currentuser)


class DnsZonePage(CommonPage):

    def __init__(self):
        super().__init__('dnszone', DnsZone, DnsZoneForm)


class DnsZoneApi(CommonApi):

    def __init__(self):
        super().__init__(DnsZone)


#
# Subnet
#

class SubnetForm(CherryForm):

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
    owner = UserField(
        _('Owner'),
        default=lambda: cherrypy.serving.request.currentuser)


class SubnetPage(CommonPage):

    def __init__(self):
        super().__init__('subnet', Subnet, SubnetForm)


class SubnetApi(CommonApi):

    def __init__(self):
        super().__init__(Subnet)

#
# DNS Record
#


class DnsRecordForm(CherryForm):

    @staticmethod
    def get_display_name():
        return _('DNS Record')

    name = StringField(
        _('Name'),
        validators=[DataRequired(), validate_domain],
        render_kw={"placeholder": _("Enter a FQDN")})

    type = DnsRecordType(
        _('Type'),
        validators=[DataRequired()])

    ttl = IntegerField(
        _('TLL'),
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

    owner = UserField(
        _('Owner'),
        default=lambda: cherrypy.serving.request.currentuser)


class DnsRecordPage(CommonPage):

    def __init__(self):
        super().__init__('dnsrecord', DnsRecord, DnsRecordForm)


class DnsRecordApi(CommonApi):

    def __init__(self):
        super().__init__(DnsRecord)


class DhcpRecordForm(CherryForm):
    """
    DHCP Record Form
    """

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

    owner = UserField(
        _('Owner'),
        default=lambda: cherrypy.serving.request.currentuser)


class DhcpRecordPage(CommonPage):

    def __init__(self):
        super().__init__('dhcprecord', DhcpRecord, DhcpRecordForm)


class DhcpRecordApi(CommonApi):

    def __init__(self):
        super().__init__(DhcpRecord)
