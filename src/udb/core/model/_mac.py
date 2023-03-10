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

import itertools

import cherrypy
import validators
from sqlalchemy import Column, String, event
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import validates

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.tools.i18n import gettext_lazy as _

from ._common import CommonMixin
from ._follower import FollowerMixin
from ._json import JsonMixin
from ._message import MessageMixin
from ._search_vector import SearchableMixing

Base = cherrypy.tools.db.get_base()

Session = cherrypy.tools.db.get_session()


class Mac(CommonMixin, JsonMixin, MessageMixin, FollowerMixin, SearchableMixing, Base):
    __tablename__ = 'mac'
    mac = Column(String, nullable=False, unique=True)

    @classmethod
    def _search_string(cls):
        return cls.mac + " " + cls.notes

    @hybrid_property
    def summary(self):
        return self.mac

    @validates('mac')
    def validate_mac(self, key, value):
        if not validators.mac_address(value):
            raise ValueError('mac', _('expected a valid mac'))
        return value


@event.listens_for(Session, "before_flush", insert=True)
def _update_mac(session, flush_context, instances):
    """
    Create missing Mac Record when creating or updating record.
    """
    for instance in itertools.chain(session.new, session.dirty):
        if hasattr(instance, '_mac_column_name'):
            # Get IP Value
            try:
                value = getattr(instance, instance._mac_column_name)
                validators.mac_address(value)
            except ValueError:
                value = None
            # Make sure to get/create unique IP record.
            # Do not assign the object as it might impact the update statement for generated column.
            if value is not None:
                instance._mac  # Fetch the MAC for history
                instance._mac = _unique_mac(session, value)


def _unique_mac(session, key):
    """
    Using a session cache, make sure to return unique Mac object.
    """
    assert key
    cache = getattr(session, '_unique_mac_cache', None)
    if cache is None:
        session._unique_mac_cache = cache = {}

    if key in cache:
        return cache[key]
    else:
        with session.no_autoflush:
            obj = session.query(Mac).filter_by(mac=key).first()
            if not obj:
                obj = Mac(mac=key)
                session.add(obj)
        cache[key] = obj
        return obj
