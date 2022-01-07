# -*- coding: utf-8 -*-
# cmdb, A web interface to manage IT network CMDB
# Copyright (C) 2021 IKUS Software inc.
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

from cmdb.core.model import User, UserLoginException


def checkpassword(realm, username, password):
    """
    Check basic authentication.
    """
    try:
        return User.login(username, password) is not None
    except UserLoginException:
        return False


@cherrypy.tools.json_out()
@cherrypy.tools.json_in()
@cherrypy.tools.sessions(on=False)
@cherrypy.tools.auth_form(on=False)
@cherrypy.tools.auth_basic(on=True, realm='cmdb-api', checkpassword=checkpassword)
class Api():
    """
    This class is a node to set all the configuration to access /api/
    """
    pass
