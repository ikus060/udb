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
import pkg_resources


@cherrypy.tools.db(on=False)
@cherrypy.tools.sessions(on=False)
@cherrypy.tools.auth_form(on=False)
@cherrypy.tools.currentuser(on=False)
@cherrypy.tools.i18n(on=False)
class Static():

    @cherrypy.expose()
    def login_bg_jpg(self):
        fn = pkg_resources.resource_filename(
            'udb.controller.static', 'taylor-vick-M5tzZtFCOfs-unsplash.jpg')
        return cherrypy.lib.static.serve_file(fn)
