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
from wtforms.fields import StringField
from wtforms.fields.simple import TextAreaField
from wtforms.validators import DataRequired, IPAddress, Length, MacAddress

from udb.core.model import DhcpRecord, User, Vrf
from udb.tools.i18n import gettext_lazy as _

from .common_page import CommonPage
from .form import CherryForm, SelectObjectField


class DhcpRecordForm(CherryForm):
    """
    DHCP Record Form
    """

    object_cls = DhcpRecord

    ip = StringField(
        _('IP'),
        validators=[DataRequired(), IPAddress(ipv4=True, ipv6=True)],
        render_kw={"placeholder": _("Enter an IPv4 or IPv6 address"), "autofocus": True, "width": "3/4"},
    )

    vrf_id = SelectObjectField(
        _('VRF'),
        object_cls=Vrf,
        render_kw={"width": "1/4"},
        description=_("Determined automatically if left blank."),
    )

    mac = StringField(
        _('MAC'), validators=[DataRequired(), MacAddress()], render_kw={"placeholder": _("Enter a MAC address")}
    )

    notes = TextAreaField(
        _('Notes'),
        default='',
        validators=[
            Length(max=256),
        ],
        render_kw={"placeholder": _("Enter details information about this DHCP Reservation")},
    )

    owner_id = SelectObjectField(
        _('Owner'),
        object_cls=User,
        default=lambda: cherrypy.serving.request.currentuser.id,
    )


class DhcpRecordPage(CommonPage):
    def __init__(self) -> None:
        super().__init__(DhcpRecord, DhcpRecordForm)

    def _list_query(self):
        return (
            DhcpRecord.query.outerjoin(DhcpRecord.owner)
            .outerjoin(DhcpRecord.vrf)
            .with_entities(
                DhcpRecord.id,
                DhcpRecord.estatus,
                DhcpRecord.ip,
                DhcpRecord.mac,
                Vrf.id,
                Vrf.name,
                DhcpRecord.notes,
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
            for row in Vrf.query.with_entities(Vrf.id, Vrf.name, func.count(DhcpRecord.id).label('count'))
            .outerjoin(DhcpRecord)
            .group_by(Vrf.id)
            .all()
        ]
        return values
