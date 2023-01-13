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
from sqlalchemy import event

import udb.tools.db  # noqa: import cherrypy.tools.db

Base = cherrypy.tools.db.get_base()

Session = cherrypy.tools.db.get_session()


class HasIpMixin(object):
    """
    Subclasses must implement `_ip` to be a relationship and `ip` as a property returning the ip address as a string.
    """

    _ip_column_name = 'ip'

    def _invalidate_ip(self, new_value, old_value, event):
        """
        Called whenever the 'ip' field get assigned.
        """
        # When the ip address get updated on a record, make sure to load the relatd Ip objectto update the history.
        if new_value != old_value:
            self._ip

    @classmethod
    def __declare_last__(cls):
        # Attach a listener on `ip` column
        ip_field = getattr(cls, cls._ip_column_name)
        event.listen(ip_field, 'set', cls._invalidate_ip)
