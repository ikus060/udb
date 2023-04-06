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
from wtforms.fields import IntegerField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from udb.core.model import DnsZone, Subnet, SubnetRange, User, Vrf
from udb.tools.i18n import gettext_lazy as _

from .common_page import CommonPage
from .form import CherryForm, DualListWidget, SelectMultipleObjectField, SelectObjectField, StringFieldSet

unset_value = "UNSET_DATA"


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


class SubnetForm(CherryForm):

    object_cls = Subnet
    name = StringField(
        _('Name'),
        validators=[Length(max=256)],
        render_kw={"placeholder": _("Enter a description"), "autofocus": True},
    )
    ranges = StringFieldSet(
        label=_('IP Ranges'),
        validators=[Length(max=256)],
        render_kw={"placeholder": _("Enter IPv4 or IPv6 address")},
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
            'width': '1/3',
            "pattern": "\\d+",
            "title": _('L3VNI number.'),
        },
    )
    l2vni = IntegerField(
        _('L2VNI'),
        validators=[Optional(), NumberRange(min=0, max=2147483647, message=_('L2VNI must be at least %(min)s.'))],
        render_kw={
            'width': '1/3',
            "pattern": "\\d+",
            "title": _('L2VNI number.'),
        },
    )
    vlan = IntegerField(
        _('VLAN'),
        validators=[Optional(), NumberRange(min=0, max=2147483647, message=_('VLAN must be at least %(min)s.'))],
        render_kw={
            'width': '1/3',
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
    )
    dnszones = SelectMultipleObjectField(
        _('Allowed DNS zone(s)'),
        object_cls=DnsZone,
        widget=DualListWidget(),
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


SubnetRow = namedtuple(
    'SubnetRow',
    [
        'id',
        'status',
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
                Subnet.status,
                Subnet.name,
                SubnetRange.vrf_id,
                Vrf.name.label('vrf_name'),
                Subnet.l3vni,
                Subnet.l2vni,
                Subnet.vlan,
                Subnet.rir_status,
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
                row['vrf_id'] != prev_row[-1]['vrf_id'] or not _subnet_of(primary_range, prev_row[-1]['primary_range'])
            ):
                prev_row.pop()
            yield SubnetRow(
                id=row.id,
                status=row.status,
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
                dnszone_names=dnszone_names,
            )
            # Keep reference of previous row for depth calculation
            if row.status != Subnet.STATUS_DELETED:
                prev_row.append(
                    {
                        'vrf_id': row.vrf_id,
                        'primary_range': primary_range,
                    }
                )
