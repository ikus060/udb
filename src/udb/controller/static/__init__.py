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
from cherrypy.lib.static import serve_file

try:
    from importlib.resources import resource_filename
except ImportError:
    # For Python 2 or Python 3 with older setuptools
    from pkg_resources import resource_filename


@cherrypy.tools.auth_form(on=False)
@cherrypy.tools.auth_mfa(on=False)
@cherrypy.tools.currentuser(on=False)
@cherrypy.tools.i18n(on=False)
@cherrypy.tools.ratelimit(on=False)
@cherrypy.tools.secure_headers(on=False)
@cherrypy.tools.sessions(on=False)
class Static:
    @cherrypy.expose
    @cherrypy.tools.staticdir(
        section="", match=".*(\\.js|\\.css|\\.png)$", dir=resource_filename('udb.controller', 'static')
    )
    def default(self, *args, **kwargs):
        """This entry point is used to serve content of /static/ folder and JinjaX static ressources"""
        # Make use of JinjaX catalog
        env = cherrypy.request.config.get('tools.jinja2.env')
        if env is None or 'catalog' not in env.globals:
            raise cherrypy.HTTPError(400)

        # JinjaX resources could be locaed in multiple path.
        jinjax_catalog = env.globals['catalog']
        for path in jinjax_catalog.paths:
            handled = cherrypy.lib.static.staticdir(section="static", match=".*(\\.js|\\.css)$", dir=path)
            if handled:
                return cherrypy.serving.response.body
        raise cherrypy.HTTPError(400)

    @cherrypy.tools.staticfile(filename=resource_filename(__name__, 'taylor-vick-M5tzZtFCOfs-unsplash.jpg'))
    def login_bg_jpg(self):
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
