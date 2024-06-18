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

import cherrypy
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import aliased
from wtforms.fields import BooleanField, FieldList, FormField, IntegerField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, StopValidation, ValidationError
from wtforms.widgets import HiddenInput

from udb.core.model import DnsZone, Subnet, User, Vrf
from udb.tools.i18n import gettext_lazy as _

from .common_page import CommonPage
from .form import CherryForm, JinjaWidget, SelectMultipleObjectField, SelectObjectField, SwitchWidget


def _subnet_of(range1, range2):
    if not range1 or not range2:
        return False
    range1 = ipaddress.ip_network(range1)
    range2 = ipaddress.ip_network(range2)
    return range1.version == range2.version and range1.subnet_of(range2)


def _norm_range(value):
    """
    Used to normalize the subnet range values without running validation.
    """
    # For empty string or None, return None
    if not value:
        return None
    # Strip the value from extra spaces.
    value = value.strip()
    # Normalize the subnet range.
    try:
        return str(ipaddress.ip_network(value))
    except Exception:
        # If the range is not valid, so we can't normalize the value.
        # Validation error will be raised.
        return value


def _norm_ipaddress(value):
    """
    Used to normalize the subnet range values without running validation.
    """
    # For empty string or None, return None
    if not value:
        return None
    # Strip the value from extra spaces.
    value = value.strip()
    # Normalize the subnet range.
    try:
        return str(ipaddress.ip_address(value))
    except Exception:
        # If the range is not valid, so we can't normalize the value.
        # Validation error will be raised.
        return value


class SubnetTableWidget(JinjaWidget):
    filename = 'widgets/SubnetTableWidget.html'


class SubnetRangeform(CherryForm):
    range = StringField(
        label=_('IP Ranges'),
        validators=[
            DataRequired(),
            Length(max=256),
        ],
        filters=[_norm_range],
        render_kw={"placeholder": _("174.95.0.0/16 or 2001:0db8:85a3::/64")},
    )
    dhcp = BooleanField(
        _('DHCP Enabled'),
        widget=SwitchWidget(),
    )
    dhcp_start_ip = StringField(
        _('DHCP Start'),
        validators=[Length(max=256)],
        filters=[_norm_ipaddress],
        render_kw={"placeholder": _("Leave blank for default")},
    )
    dhcp_end_ip = StringField(
        _('DHCP Stop'),
        validators=[Length(max=256)],
        filters=[_norm_ipaddress],
        render_kw={"placeholder": _("Leave blank for default")},
    )
    status = IntegerField(widget=HiddenInput(), validators=[Optional()])
    id = IntegerField(widget=HiddenInput(), validators=[Optional()])

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
    ranges = FieldList(
        FormField(SubnetRangeform, default=Subnet),
        label=_('IP Ranges'),
        widget=SubnetTableWidget(),
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
        validators=[
            Optional(),
            NumberRange(
                min=1,
                max=16777215,
                message=_('The Layer 3 Virtual Network Identifier can range from %(min)s to %(max)s.'),
            ),
        ],
        render_kw={
            'width': '1/4',
            "pattern": "\\d+",
            "title": _('Layer 3 Virtual Network Identifier'),
        },
    )
    l2vni = IntegerField(
        _('L2VNI'),
        validators=[
            Optional(),
            NumberRange(
                min=1,
                max=16777215,
                message=_('The Layer 2 Virtual Network Identifier can range from %(min)s to %(max)s.'),
            ),
        ],
        render_kw={
            'width': '1/4',
            "pattern": "\\d+",
            "title": _('Layer 2 Virtual Network Identifier'),
        },
    )
    vlan = IntegerField(
        _('VLAN'),
        validators=[
            Optional(),
            NumberRange(min=1, max=4095, message=_('The VLAN ID can range from %(min)s to %(max)s.')),
        ],
        render_kw={
            'width': '1/4',
            "pattern": "\\d+",
            "title": _('Virtual Local Area Network ID'),
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
        # Populate fields from object data. Except ranges
        formdata = self.meta.wrap_formdata(self, formdata)
        if data is not None:
            kwargs = dict(data, **kwargs)
        for (name, field) in self._fields.items():
            if obj is not None and field.name == 'ranges':
                field.process(formdata, [obj] + list(obj.slave_subnets))
            elif obj is not None and hasattr(obj, name):
                field.process(formdata, getattr(obj, name))
            elif name in kwargs:
                field.process(formdata, kwargs[name])
            else:
                field.process(formdata)

    def populate_obj(self, obj):
        # Populate object from form data. Except slave_subnets
        for name, field in self._fields.items():
            if field.name == 'ranges' or (field.render_kw and field.render_kw.get('readonly')):
                continue
            field.populate_obj(obj, name)
        # Populate subnet ranges with a custom implementation to avoid unwanted effect.
        # Lookup subnet by id.
        obj_slave_subnets = list(obj.slave_subnets) + [obj]
        for form_subnet_range in self.ranges:
            range_id = form_subnet_range.data.get('id')
            match = [r for r in obj_slave_subnets if r.id == range_id]
            if match:
                match = match[0]
                obj_slave_subnets.remove(match)
            elif range_id:
                raise ValueError('subnet range cannot be found in database')
            else:
                # Row without ID are new row.
                match = Subnet(range=form_subnet_range.range.data).add()
                obj.slave_subnets.append(match)
            # Then use default implementation to populate the subnet range.
            form_subnet_range.form.populate_obj(match)


class SubnetPage(CommonPage):
    def __init__(self):
        super().__init__(Subnet, SubnetForm, new_perm=User.PERM_SUBNET_CREATE)

    @cherrypy.expose
    @cherrypy.tools.jinja2(template=['subnet/edit.html'])
    def edit(self, key, **kwargs):
        """
        Make slave subnet not editable.
        """
        values = super().edit(key, **kwargs)
        obj = values['obj']
        if obj.slave:
            values['edit_perm'] = False
        return values

    def _list_query(self):
        # This implementation must return the list of subnets with
        # 1. `order` field based on range
        # 2. `secondary_range` that contains all range but the primary
        # 3. `dhcp` field with "1 on 2" to show the number of range with enabled DHCP
        # 4. `dnszone_names` with all supported zone.
        a1 = aliased(Subnet)
        slave_ranges = (
            a1.query.with_entities(func.group_concat(a1.range.text()))
            .filter(a1.parent_id == Subnet.id, a1.slave.is_(True), a1.estatus != Subnet.STATUS_DELETED)
            .scalar_subquery()
        )
        a2 = aliased(Subnet)
        dhcp = (
            a2.query.with_entities(
                func.format(
                    str(_('%s on %s')),
                    func.count(case((a2.dhcp.is_(True), a2.id)).distinct()),
                    func.count(a2.id.distinct()),
                )
            )
            .filter(or_(a2.id == Subnet.id, and_(a2.parent_id == Subnet.id, a2.slave.is_(True))))
            .scalar_subquery()
        )
        a3 = aliased(Subnet)
        dnszone_names = (
            DnsZone.query.with_entities(func.group_concat(DnsZone.name))
            .join(a3, DnsZone.subnets)
            .filter(DnsZone.estatus != DnsZone.STATUS_DELETED, a3.id == Subnet.id)
            .scalar_subquery()
        )
        query = (
            Subnet.query.join(Subnet.vrf)
            .filter(Subnet.slave.is_(False))
            .with_entities(
                Subnet.id,
                Subnet.estatus,
                func.row_number()
                .over(
                    order_by=(
                        Subnet.vrf_id,
                        -func.family(Subnet.range),
                        Subnet.range,
                    )
                )
                .label('order'),
                Subnet.depth,
                Subnet.range,
                slave_ranges.label('slave_ranges'),
                Subnet.name,
                Vrf.name.label('vrf_name'),
                Subnet.el3vni,
                Subnet.el2vni,
                Subnet.evlan,
                Subnet.rir_status,
                dhcp.label('dhcp'),
                dnszone_names.label('dnszone_names'),
            )
        )
        return query
