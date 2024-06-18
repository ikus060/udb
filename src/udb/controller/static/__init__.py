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
from cherrypy.lib.static import serve_file

try:
    from importlib.resources import resource_filename
except ImportError:
    # For Python 2 or Python 3 with older setuptools
    from pkg_resources import resource_filename


@cherrypy.tools.auth_form(on=False)
@cherrypy.tools.auth_mfa(on=False)
@cherrypy.tools.currentuser(on=False)
@cherrypy.tools.db(on=False)
@cherrypy.tools.i18n(on=False)
@cherrypy.tools.ratelimit(on=False)
@cherrypy.tools.secure_headers(on=False)
@cherrypy.tools.sessions(on=False)
class Static:
    @cherrypy.tools.staticdir(section="", dir=resource_filename(__name__, 'bootstrap5'))
    def bootstrap5(*args, **kwargs):
        raise cherrypy.HTTPError(400)

    @cherrypy.tools.staticdir(section="", dir=resource_filename(__name__, 'datatables'))
    def datatables(*args, **kwargs):
        raise cherrypy.HTTPError(400)

    @cherrypy.tools.staticdir(section="", dir=resource_filename(__name__, 'jquery'))
    def jquery(*args, **kwargs):
        raise cherrypy.HTTPError(400)

    @cherrypy.tools.staticdir(section="", dir=resource_filename(__name__, 'typeahead'))
    def typeahead(*args, **kwargs):
        raise cherrypy.HTTPError(400)

    @cherrypy.tools.staticdir(section="", dir=resource_filename(__name__, 'multi'))
    def multi(*args, **kwargs):
        raise cherrypy.HTTPError(400)

    @cherrypy.tools.staticfile(filename=resource_filename(__name__, 'taylor-vick-M5tzZtFCOfs-unsplash.jpg'))
    def login_bg_jpg(self):
        raise cherrypy.HTTPError(400)

    @cherrypy.tools.staticfile(filename=resource_filename(__name__, 'main.css'))
    def main_css(self):
        raise cherrypy.HTTPError(400)

    @cherrypy.tools.staticfile(filename=resource_filename(__name__, 'main.js'))
    def main_js(self):
        raise cherrypy.HTTPError(400)

    @cherrypy.tools.staticdir(section="", dir=resource_filename(__name__, 'popper.js'))
    def popper_js(self):
        raise cherrypy.HTTPError(400)

    @cherrypy.expose
    def header_logo(self, **kwargs):
        cfg = cherrypy.tree.apps[''].cfg
        filename = cfg.header_logo if cfg.header_logo else resource_filename('udb.controller.static', 'udb-logo.png')
        return serve_file(filename)

    @cherrypy.expose
    def favicon(self, **kwargs):
        cfg = cherrypy.tree.apps[''].cfg
        filename = cfg.favicon if cfg.favicon else resource_filename('udb.controller.static', 'udb_16.svg')
        return serve_file(filename)

    favicon_ico = favicon
