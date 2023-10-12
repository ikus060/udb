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

import ipaddress
from collections import namedtuple

import cherrypy
from sqlalchemy import case, func
from wtforms.fields import BooleanField, FieldList, FormField, IntegerField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, StopValidation, ValidationError

from udb.core.model import DnsZone, Subnet, SubnetRange, User, Vrf
from udb.tools.i18n import gettext_lazy as _

from .common_page import CommonPage
from .form import CherryForm, EditableTableWidget, SelectMultipleObjectField, SelectObjectField, Strip, SwitchWidget


def _subnet_of(range1, range2):
    if not range1 or not range2:
        return False
    range1 = ipaddress.ip_network(range1)
    range2 = ipaddress.ip_network(range2)
    return range1.version == range2.version and range1.subnet_of(range2)


def _sort_ranges(ranges):
    """
    Sort the ranges fields to place ipv6 first, then ipv4.
    """
    if not ranges:
        return None
    ranges = [ipaddress.ip_network(r) for r in ranges]
    ranges = sorted(ranges, key=lambda r: (-r.version, r.network_address.packed))
    return [r.compressed for r in ranges]


class SubnetRangeform(CherryForm):
    range = StringField(
        label=_('IP Ranges'),
        validators=[
            DataRequired(),
            Length(max=256),
        ],
        filters=[Strip()],
        render_kw={"placeholder": _("174.95.0.0/16 or 2001:0db8:85a3::/64")},
    )
    dhcp = BooleanField(
        _('DHCP Enabled'),
        widget=SwitchWidget(),
    )
    dhcp_start_ip = StringField(
        _('DHCP Start'),
        validators=[Length(max=256)],
        filters=[Strip()],
        render_kw={"placeholder": _("Leave blank for default")},
    )
    dhcp_end_ip = StringField(
        _('DHCP Stop'),
        validators=[Length(max=256)],
        filters=[Strip()],
        render_kw={"placeholder": _("Leave blank for default")},
    )

    def validate_range(self, field):
        try:
            ipaddress.ip_network(field.data)
        except ValueError:
            raise StopValidation(_('%s is not a valid IPv4 or IPv6 range') % field.data)

    def validate_dhcp_start_ip(self, field):
        try:
            network = ipaddress.ip_network(self.range.data)
        except Exception:
            # Skip validation if the range is invalid.
            return
        # Generate default value when empty.
        if self.dhcp.data and not field.data:
            field.data = str(network.network_address + 1)
        # Validate value
        if field.data:
            # Make sure it's a valid ip address
            try:
                address = ipaddress.ip_address(field.data)
            except ValueError:
                raise ValidationError(_('%s is not a valid IPv4 or IPv6 address') % field.data)
            # Check if ip within range
            if not (network.network_address < address and address < network.broadcast_address):
                raise ValidationError(_('DHCP start must be defined within the subnet range'))

    def validate_dhcp_end_ip(self, field):
        try:
            network = ipaddress.ip_network(self.range.data)
        except Exception:
            # Skip validation if the range is invalid.
            return
        # Generate default value when empty.
        if self.dhcp.data and not field.data:
            if network.version == 4:
                field.data = str(network.broadcast_address - 1)
            else:
                field.data = str(network.broadcast_address)
        # Validate value
        if field.data:
            # Make sure it's a valid ip address
            try:
                address = ipaddress.ip_address(field.data)
            except ValueError:
                raise ValidationError(_('%s is not a valid IPv4 or IPv6 address') % field.data)
            # Check if ip within range
            if (
                network.network_address >= address
                or (network.version == 4 and address >= network.broadcast_address)
                or (network.version == 6 and address > network.broadcast_address)
            ):
                raise ValidationError(_('DHCP end must be defined within the subnet range'))
            # Check if end_ip it greather than start_ip
            try:
                start_ip = ipaddress.ip_address(self.dhcp_start_ip.data)
            except Exception:
                # Skip validation if the start_ip is invalid.
                return
            if start_ip >= address:
                raise ValidationError(_('DHCP end must be greather than DHCP start'))


class SubnetForm(CherryForm):

    object_cls = Subnet
    name = StringField(
        _('Name'),
        validators=[Length(max=256)],
        render_kw={"placeholder": _("Enter a description"), "autofocus": True},
    )
    subnet_ranges = FieldList(
        FormField(SubnetRangeform, default=SubnetRange),
        label=_('IP Ranges'),
        widget=EditableTableWidget(),
        min_entries=1,
        max_entries=100,
    )
    vrf_id = SelectObjectField(
        _('VRF'),
        object_cls=Vrf,
        validators=[DataRequired()],
        render_kw={"placeholder": _("Enter a VRF number (optional)")},
    )
    l3vni = IntegerField(
        _('L3VNI'),
        validators=[Optional(), NumberRange(min=0, max=2147483647, message=_('L3VNI must be at least %(min)s.'))],
        render_kw={
            'width': '1/4',
            "pattern": "\\d+",
            "title": _('L3VNI number.'),
        },
    )
    l2vni = IntegerField(
        _('L2VNI'),
        validators=[Optional(), NumberRange(min=0, max=2147483647, message=_('L2VNI must be at least %(min)s.'))],
        render_kw={
            'width': '1/4',
            "pattern": "\\d+",
            "title": _('L2VNI number.'),
        },
    )
    vlan = IntegerField(
        _('VLAN'),
        validators=[Optional(), NumberRange(min=0, max=2147483647, message=_('VLAN must be at least %(min)s.'))],
        render_kw={
            'width': '1/4',
            "pattern": "\\d+",
            "title": _('VLAN number.'),
        },
    )
    rir_status = SelectField(
        _('RIR Status'),
        choices=[
            ('', _("-")),
            (Subnet.RIR_STATUS_ASSIGNED, Subnet.RIR_STATUS_ASSIGNED),
            (Subnet.RIR_STATUS_ALLOCATED_BY_LIR, Subnet.RIR_STATUS_ALLOCATED_BY_LIR),
        ],
        validators=[Optional()],
        coerce=lambda value: value if value else None,
        default='',
        render_kw={
            'width': '1/4',
        },
    )
    dnszones = SelectMultipleObjectField(
        _('Allowed DNS zone(s)'),
        object_cls=DnsZone,
        render_kw={
            "class": "multi",
            "data-non_selected_header": _("Available"),
            "data-selected_header": _("Selected"),
            "data-search_placeholder": _("Filter..."),
        },
    )
    notes = TextAreaField(
        _('Notes'),
        default='',
        validators=[Length(max=256)],
        render_kw={"placeholder": _("Enter details information about this subnet")},
    )
    owner_id = SelectObjectField(
        _('Owner'),
        object_cls=User,
        default=lambda: cherrypy.serving.request.currentuser.id,
    )

    def process(self, formdata=None, obj=None, data=None, **kwargs):
        """
        Custom implementation to take account of subnet-ranges fields.
        """
        super().process(formdata, obj, data=data, **kwargs)

        # When subnet ranges are not defined in formdata, let used the value from the object instead of replacing the value with empty array.
        if formdata:
            subnet_range_defined = list(self.subnet_ranges._extract_indices(self.subnet_ranges.name, formdata))
            if not subnet_range_defined:
                self.subnet_ranges.process(None, obj.subnet_ranges)


SubnetRow = namedtuple(
    'SubnetRow',
    [
        'id',
        'estatus',
        'order',
        'depth',
        'primary_range',
        'secondary_ranges',
        'name',
        'vrf_name',
        'l3vni',
        'l2vni',
        'vlan',
        'rir_status',
        'dhcp',
        'dnszone_names',
    ],
)


class SubnetPage(CommonPage):
    def __init__(self):
        super().__init__(Subnet, SubnetForm, new_perm=User.PERM_SUBNET_CREATE)

    def _list_query(self):

        query = (
            Subnet.query.join(Subnet.subnet_ranges)
            .outerjoin(Subnet.dnszones)
            .join(Subnet.vrf)
            .group_by(Subnet.id, SubnetRange.vrf_id, Vrf.name)
            .with_entities(
                Subnet.id,
                Subnet.estatus,
                Subnet.name,
                SubnetRange.vrf_id,
                Vrf.name.label('vrf_name'),
                Subnet.l3vni,
                Subnet.l2vni,
                Subnet.vlan,
                Subnet.rir_status,
                func.format(
                    str(_('%s on %s')),
                    func.count(case((SubnetRange.dhcp.is_(True), SubnetRange.id)).distinct()),
                    func.count(SubnetRange.id.distinct()),
                ).label('dhcp'),
                func.group_concat(SubnetRange.range.text().distinct()).label('ranges'),
                func.group_concat(DnsZone.name.distinct()).label('dnszone_names'),
            )
            .order_by(
                SubnetRange.vrf_id,
                func.min(case((SubnetRange.version == 6, SubnetRange.range), else_=None)),
                func.min(case((SubnetRange.version == 4, SubnetRange.range), else_=None)),
            )
        )
        rows = query.all()

        # Update depth & orer
        order = 0
        prev_row = []
        for i in range(0, len(rows)):
            row = rows[i]
            # SQLite and Postgresql behave differently when ordering, so let re-order the subnet range in python.
            ranges = _sort_ranges(row.ranges.split(','))
            primary_range = ranges[0] if ranges else None
            secondary_ranges = ', '.join(ranges[1:]) if ranges else None
            # Replace single comma
            dnszone_names = ', '.join(row.dnszone_names.split(',')) if row.dnszone_names else None
            # Re-create a new row
            order = order + 1
            # Compute depth
            while prev_row and (
                row.vrf_id != prev_row[-1]['vrf_id'] or not _subnet_of(primary_range, prev_row[-1]['primary_range'])
            ):
                prev_row.pop()
            yield SubnetRow(
                id=row.id,
                estatus=row.estatus,
                order=order,
                depth=len(prev_row),
                primary_range=primary_range,
                secondary_ranges=secondary_ranges,
                name=row.name,
                vrf_name=row.vrf_name,
                l3vni=row.l3vni,
                l2vni=row.l2vni,
                vlan=row.vlan,
                rir_status=row.rir_status,
                dhcp=row.dhcp,
                dnszone_names=dnszone_names,
            )
            # Keep reference of previous row for depth calculation
            if row.estatus != Subnet.STATUS_DELETED:
                prev_row.append(
                    {
                        'vrf_id': row.vrf_id,
                        'primary_range': primary_range,
                    }
                )
