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
import validators
from sqlalchemy import Column, ForeignKey, Index, event, func, literal, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import aliased, relationship, validates
from sqlalchemy.types import String

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.tools.i18n import gettext_lazy as _

from ._cidr import InetType
from ._common import CommonMixin
from ._follower import FollowerMixin
from ._json import JsonMixin
from ._message import MessageMixin
from ._rule import rule
from ._search_string import SearchableMixing
from ._status import StatusMixing
from ._subnet import Subnet, SubnetRange

Base = cherrypy.tools.db.get_base()

Session = cherrypy.tools.db.get_session()


class DhcpRecord(CommonMixin, JsonMixin, StatusMixing, MessageMixin, FollowerMixin, SearchableMixing, Base):
    _ip_column_name = 'ip'
    _mac_column_name = 'mac'

    ip = Column(InetType, ForeignKey("ip.ip"), nullable=False)
    _ip = relationship("Ip", back_populates='related_dhcp_records', lazy=True)
    mac = Column(String, ForeignKey("mac.mac"), nullable=False)
    _mac = relationship("Mac", backref='related_dhcp_records', lazy=True)

    @classmethod
    def _search_string(cls):
        return cls.mac + " " + cls.notes

    @validates('ip')
    def validate_ip(self, key, value):
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            raise ValueError('ip', _('value must be a valid IP address'))

    @validates('mac')
    def validate_mac(self, key, value):
        if not validators.mac_address(value):
            raise ValueError('mac', _('expected a valid mac'))
        return value

    def __str__(self):
        return "%s (%s)" % (self.ip, self.mac)

    @hybrid_property
    def summary(self):
        return self.ip + " (" + self.mac + ")"

    @summary.expression
    def summary(self):
        return self.ip.host() + " (" + self.mac + ")"

    def _validate(self):
        """
        Run other validation on all fields.
        """
        # IP should be within a Subnet
        if not self._ip.related_subnets:
            raise ValueError('ip', _('IP address must be defined within a Subnet'))


Index('dhcprecord_mac_key', DhcpRecord.mac, unique=True)


@event.listens_for(DhcpRecord.ip, 'set')
def dhcp_reload_ip(self, new_value, old_value, initiator):
    # When the ip address get updated on a record, make sure to load the relatd Ip object to update the history.
    if new_value != old_value:
        self._ip


@event.listens_for(DhcpRecord.mac, 'set')
def dns_reload_mac(self, new_value, old_value, initiator):
    # When the ip address get updated on a record, make sure to load the relatd Ip object to update the history.
    if new_value != old_value:
        self._mac


@event.listens_for(DhcpRecord, "before_update")
def before_update(mapper, connection, instance):
    instance._validate()


@event.listens_for(DhcpRecord, "before_insert")
def before_insert(mapper, connection, instance):
    instance._validate()


@rule(DhcpRecord, _('DHCP has been disabled on this subnet.'))
def dhcprecord_invalid_subnet():
    """
    Return a query listing all the dhcp record without a valid subnet
    """
    # For each PTR Record, check if the IP ddress matches the IP address of the forward record (A, AAAA).
    return select(DhcpRecord.id.label('id'), DhcpRecord.summary.label('name'),).filter(
        ~(
            select(Subnet.id)
            .join(Subnet.subnet_ranges)
            .filter(
                Subnet.dhcp.is_(True),
                SubnetRange.version == func.family(DhcpRecord.ip),
                SubnetRange.start_ip <= func.inet(DhcpRecord.ip),
                SubnetRange.end_ip > func.inet(DhcpRecord.ip),
                Subnet.status == Subnet.STATUS_ENABLED,
                DhcpRecord.status == DhcpRecord.STATUS_ENABLED,
            )
            .exists()
        )
    )


@rule(DhcpRecord, _('Multiple DHCP Reservation for the same IP address.'))
def dhcprecord_unique_ip():
    """
    Return a list of record with identical IP.
    """
    a = aliased(DhcpRecord)
    return (
        select(
            DhcpRecord.id.label('id'),
            DhcpRecord.summary.label('name'),
            a.id.label('other_id'),
            literal(DhcpRecord.__tablename__).label('other_model_name'),
            a.summary.label('other_name'),
        )
        .join(a, DhcpRecord.ip == a.ip)
        .filter(
            DhcpRecord.id != a.id,
            DhcpRecord.status == DhcpRecord.STATUS_ENABLED,
            a.status == DhcpRecord.STATUS_ENABLED,
        )
    )
