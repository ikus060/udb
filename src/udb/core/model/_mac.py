# udb, A web interface to manage IT network
# Copyright (C) 2022-2026 IKUS Software inc.
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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


import cherrypy
import validators
from cherrypy_foundation.tools.i18n import gettext_lazy as _
from sqlalchemy import Column, Index, String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import validates

from ._common import CommonMixin
from ._follower import FollowerMixin
from ._json import JsonMixin
from ._message import MessageMixin
from ._search_string import SearchableMixing

Base = cherrypy.db.base


class Mac(CommonMixin, JsonMixin, MessageMixin, FollowerMixin, SearchableMixing, Base):
    __tablename__ = 'mac'
    mac = Column(String, nullable=False)

    @classmethod
    def _search_string(cls):
        return cls.mac + " " + cls.notes

    @classmethod
    def unique_mac(cls, key):
        """
        Using a session cache, make sure to return unique Mac object.
        """
        assert key
        session = cherrypy.db.session
        # Search current sessions for matching IP
        matching_mac = next((obj for obj in session.new if isinstance(obj, Mac) and obj.mac == key), None)
        if matching_mac:
            return matching_mac
        # If not found in our session, search database.
        obj = Mac.query.filter_by(mac=key).first()
        if obj:
            return obj
        # If not found in database, create it.
        return Mac(mac=key).add()

    @hybrid_property
    def summary(self):
        return self.mac

    @validates('mac')
    def validate_mac(self, key, value):
        # Validated at application level to avoid Postgresql raising exception
        if not validators.mac_address(value):
            raise ValueError('mac', _('expected a valid mac'))
        return value


Index(
    'mac_mac_unique_ix',
    Mac.mac,
    unique=True,
    info={
        'description': _('A MAC address must be unique.'),
    },
)
