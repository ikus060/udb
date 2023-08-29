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
from sqlalchemy import Column, ForeignKey, Index, and_, event, func, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import aliased, declared_attr, foreign, relationship, remote, validates
from sqlalchemy.types import String

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.tools.i18n import gettext_lazy as _

from ._cidr import InetType
from ._common import CommonMixin
from ._dnsrecord import DnsRecord
from ._follower import FollowerMixin
from ._json import JsonMixin
from ._message import MessageMixin
from ._rule import Rule, RuleConstraint
from ._search_string import SearchableMixing
from ._status import StatusMixing
from ._subnet import Subnet, SubnetRange

Base = cherrypy.tools.db.get_base()


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
        # Validated at application level to avoid Postgresql raising exception
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            raise ValueError('ip', _('value must be a valid IP address'))

    @validates('mac')
    def validate_mac(self, key, value):
        # Validated at application level to avoid Postgresql raising exception
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

    @declared_attr
    def related_ptr_dnsrecord(cls):
        return relationship(
            DnsRecord,
            primaryjoin=and_(
                remote(foreign(DnsRecord.generated_ip)) == cls.ip,
                DnsRecord.type.in_(['PTR', 'A', 'AAAA']),
                DnsRecord.status == DnsRecord.STATUS_ENABLED,
            ),
            lazy=True,
            viewonly=True,
        )


Index(
    'dhcprecord_mac_key',
    DhcpRecord.mac,
    unique=True,
    sqlite_where=DhcpRecord.status == DhcpRecord.STATUS_ENABLED,
    postgresql_where=DhcpRecord.status == DhcpRecord.STATUS_ENABLED,
    info={
        'description': _('A DHCP Reservation already exists for this MAC address.'),
        'field': 'mac',
        'related': lambda obj: DhcpRecord.query.filter(
            DhcpRecord.status == DhcpRecord.STATUS_ENABLED, DhcpRecord.mac == obj.mac
        ).first(),
    },
)


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


RuleConstraint(
    name="dhcprecord_ip_without_subnet",
    model=DhcpRecord,
    severity=Rule.SEVERITY_ENFORCED,
    statement=select(DhcpRecord.id, DhcpRecord.summary.label('name')).filter(
        DhcpRecord.status == DhcpRecord.STATUS_ENABLED,
        ~(
            select(Subnet.id)
            .join(Subnet.subnet_ranges)
            .filter(
                SubnetRange.version == func.family(DhcpRecord.ip),
                SubnetRange.start_ip <= DhcpRecord.ip,
                SubnetRange.end_ip >= DhcpRecord.ip,
                Subnet.status == Subnet.STATUS_ENABLED,
            )
            .exists()
        ),
    ),
    info={
        'description': _("IP address must be defined within a Subnet."),
        'field': 'ip',
    },
)

RuleConstraint(
    name="dhcprecord_invalid_subnet",
    model=DhcpRecord,
    statement=select(DhcpRecord.id.label('id'), DhcpRecord.summary.label('name'),).filter(
        DhcpRecord.status == DhcpRecord.STATUS_ENABLED,
        ~(
            select(Subnet.id)
            .join(Subnet.subnet_ranges)
            .filter(
                SubnetRange.dhcp.is_(True),
                SubnetRange.version == func.family(DhcpRecord.ip),
                SubnetRange.dhcp_start_ip <= DhcpRecord.ip,
                SubnetRange.dhcp_end_ip >= DhcpRecord.ip,
                Subnet.status == Subnet.STATUS_ENABLED,
            )
            .exists()
        ),
    ),
    info={
        'description': _("DHCP Reservation is outside of DHCP range or DHCP is disabled."),
        'field': 'ip',
    },
)


RuleConstraint(
    name="dhcprecord_unique_ip",
    model=DhcpRecord,
    statement=(
        lambda: (a := aliased(DhcpRecord))
        and (
            select(
                DhcpRecord.id.label('id'),
                DhcpRecord.summary.label('name'),
            )
            .join(a, DhcpRecord.ip == a.ip)
            .filter(
                DhcpRecord.id != a.id,
                DhcpRecord.status == DhcpRecord.STATUS_ENABLED,
                a.status == DhcpRecord.STATUS_ENABLED,
            )
            .distinct()
        )
    ),
    info={
        'description': _('Multiple DHCP Reservation for the same IP address.'),
        'field': 'ip',
    },
)
