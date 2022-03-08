# -*- coding: utf-8 -*-
# udb, A web interface to manage IT network
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

from udb.tools.auth_form import SESSION_KEY


class LogoutPage:
    @cherrypy.expose
    @cherrypy.tools.auth_form(on=False)
    def index(self):
        # Remove session key
        cherrypy.session[SESSION_KEY] = None
        # Redirect users to loginn page
        raise cherrypy.HTTPRedirect('/login/')
