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

SESSION_KEY = '_cp_username'


def check_formauth(login_url='/login/'):
    """A tool that looks in config for 'auth.require'. If found and it
    is not None, a login is required and the entry is evaluated as a list of
    conditions that the user must fulfill"""
    conditions = cherrypy.request.config.get('formauth.require', [])
    username = cherrypy.session.get(SESSION_KEY)
    if username:
        cherrypy.request.login = username
        for condition in conditions:
            # A condition is just a callable that returns true or false
            if not condition():
                raise cherrypy.HTTPError(status=403)
    else:
        raise cherrypy.HTTPRedirect(login_url)


cherrypy.tools.formauth = cherrypy.Tool('before_handler', check_formauth)
