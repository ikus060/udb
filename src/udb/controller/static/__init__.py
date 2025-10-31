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
import importlib.resources

import cherrypy
from cherrypy.lib.static import serve_file
from cherrypy_foundation.components import StaticMiddleware


@cherrypy.tools.auth(on=False)
@cherrypy.tools.auth_mfa(on=False)
@cherrypy.tools.i18n(on=False)
@cherrypy.tools.ratelimit(on=False)
@cherrypy.tools.secure_headers(on=False)
@cherrypy.tools.sessions(on=False)
class Static:

    components = StaticMiddleware()

    @cherrypy.tools.staticfile(
        filename=str(importlib.resources.files(__name__) / 'taylor-vick-M5tzZtFCOfs-unsplash.jpg')
    )
    def login_bg_jpg(self):
        raise cherrypy.HTTPError(400)

    @cherrypy.expose
    def header_logo(self, **kwargs):
        cfg = cherrypy.tree.apps[''].cfg
        filename = (
            cfg.header_logo
            if cfg.header_logo
            else str(importlib.resources.files('udb.controller.static') / 'udb-logo.png')
        )
        return serve_file(filename)

    @cherrypy.expose
    def favicon(self, **kwargs):
        cfg = cherrypy.tree.apps[''].cfg
        filename = (
            cfg.favicon if cfg.favicon else str(importlib.resources.files('udb.controller.static') / 'udb_16.svg')
        )
        return serve_file(filename)

    favicon_ico = favicon

    @cherrypy.tools.staticfile(filename=str(importlib.resources.files(__name__) / 'main.css'))
    def main_css(self):
        raise cherrypy.HTTPError(400)
