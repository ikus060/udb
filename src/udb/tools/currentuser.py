# udb, A web interface to manage IT network
# Copyright (C) 2022-2025 IKUS Software inc.
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


def get_currentuser(userobj_func):
    """
    When session is enabled and user is authenticated, get the
    current user object and store it into the session as `cherrypy.serving.request.currentuser`.

    userobj_func: Define a function to be called with the value of `cherrypy.serving.request.login`.
                  This should be used to create a user object.
    """
    # Previous hooks should define 'login'. If not we raise Error 403.
    login = getattr(cherrypy.serving.request, 'login', False)
    if not login:
        raise cherrypy.HTTPError(403)

    # Query user object
    currentuser = userobj_func(login)
    if not currentuser:
        raise cherrypy.HTTPError(403)

    cherrypy.serving.request.currentuser = currentuser


cherrypy.tools.currentuser = cherrypy.Tool('before_handler', get_currentuser, priority=74)
