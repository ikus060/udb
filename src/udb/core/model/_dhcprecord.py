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
from sqlalchemy import Column, ForeignKey
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, validates
from sqlalchemy.types import String

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.tools.i18n import gettext_lazy as _

from ._cidr import InetType
from ._common import CommonMixin
from ._follower import FollowerMixin
from ._ip_mixin import HasIpMixin
from ._json import JsonMixin
from ._message import MessageMixin
from ._search_vector import SearchableMixing
from ._status import StatusMixing

Base = cherrypy.tools.db.get_base()

Session = cherrypy.tools.db.get_session()


class DhcpRecord(CommonMixin, JsonMixin, StatusMixing, MessageMixin, FollowerMixin, SearchableMixing, HasIpMixin, Base):
    ip = Column(InetType, ForeignKey("ip.ip"), nullable=False)
    mac = Column(String, nullable=False, unique=True)
    _ip = relationship("Ip", back_populates='related_dhcp_records', lazy=True)

    @classmethod
    def _search_string(cls):
        return " " + cls.mac + " " + cls.notes

    @validates('ip')
    def validate_ip(self, key, value):
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            raise ValueError('ip', _('expected a valid ipv4 or ipv6'))

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
