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


def checkpassword(realm, username, password):
    """
    We need to combine check passwork with rate limit to
    flexibly block brute force attack for unknown user.
    """
    # Use login plugin to validate user's credentials
    valid = any(cherrypy.engine.publish('login', username, password))
    if not valid:
        # When invalid, we need to increase the rate limit.
        cherrypy.tools.ratelimit.hit()
    return valid


@cherrypy.tools.json_out()
@cherrypy.tools.json_in()
@cherrypy.tools.sessions(on=False)
@cherrypy.tools.auth_form(on=False)
@cherrypy.tools.ratelimit(scope='udb-api', hit=0, priority=69)
@cherrypy.tools.auth_basic(on=True, realm='udb-api', checkpassword=checkpassword, priority=70)
class Api:
    """
    This class is a node to set all the configuration to access /api/
    """

    @cherrypy.expose
    def index(self, *kwargs):
        return {'status': 'OK'}
