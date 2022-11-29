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
import itertools

import cherrypy
from sqlalchemy import Column, Index, event
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import validates

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.tools.i18n import gettext_lazy as _

from ._cidr import InetType
from ._common import CommonMixin
from ._follower import FollowerMixin
from ._json import JsonMixin
from ._message import MessageMixin
from ._subnet import Subnet, SubnetRange

Base = cherrypy.tools.db.get_base()

Session = cherrypy.tools.db.get_session()


class Ip(CommonMixin, JsonMixin, MessageMixin, FollowerMixin, Base):
    __tablename__ = 'ip'
    ip = Column(InetType, nullable=False)

    @hybrid_property
    def summary(self):
        return self.ip

    @validates('ip')
    def validate_ip(self, key, value):
        try:
            ipaddress.ip_address(value)
        except ValueError:
            raise ValueError('ip', _('expected a valid ipv4 or ipv6'))
        return value

    @property
    def related_subnets(self):
        return (
            Subnet.query.join(Subnet.subnet_ranges)
            .filter(
                SubnetRange.range.supernet_of(str(self.ip)),
                Subnet.status != Subnet.STATUS_DELETED,
            )
            .all()
        )


# Make the IP unique
Index('ip_unique_index', Ip.ip, unique=True)


class HasIpMixin(object):
    """
    Subclasses must implement `_ip` to be a relationship and `ip` as a property returning the ip address as a string.
    """

    _ip_column_name = 'ip'


@event.listens_for(Session, "before_flush", insert=True)
def _update_ip(session, flush_context, instances):
    """
    Create missing IP Record when creating or updating record.
    """
    for instance in itertools.chain(session.new, session.dirty):
        if isinstance(instance, HasIpMixin):
            # Get IP Value
            try:
                value = getattr(instance, instance._ip_column_name)
                value = ipaddress.ip_address(value).exploded
            except ValueError:
                value = None
            # Make sure to get/create unique IP record.
            # Do not assign the object as it might impact the update statement for generated column.
            if value is not None:
                instance._ip = _unique_ip(session, value)


def _unique_ip(session, key):
    """
    Using a session cache, make sure to return unique IP object.
    """
    assert key
    cache = getattr(session, '_unique_ip_cache', None)
    if cache is None:
        session._unique_ip_cache = cache = {}

    if key in cache:
        return cache[key]
    else:
        with session.no_autoflush:
            obj = session.query(Ip).filter_by(ip=key).first()
            if not obj:
                obj = Ip(ip=key)
                session.add(obj)
        cache[key] = obj
        return obj
