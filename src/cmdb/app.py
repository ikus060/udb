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

import logging

import cherrypy
import jinja2
import pkg_resources

import cmdb.tools.db  # noqa: import cherrypy.tools.db
import cmdb.tools.formauth  # noqa: import cherrypy.tools.formauth
import cmdb.tools.jinja2  # noqa: import cherrypy.tools.jinja2
from cmdb.controller import template_processor
from cmdb.controller.login import LoginPage
from cmdb.controller.logout import LogoutPage
from cmdb.core.model import Base
from cmdb.tools.i18n import gettext, ngettext

logger = logging.getLogger(__name__)


#
# Create singleton Jinja2 environement.
#
env = jinja2.Environment(
    loader=jinja2.PackageLoader('cmdb'),
    auto_reload=True,
    autoescape=True,
    extensions=[
        'jinja2.ext.i18n',
        'jinja2.ext.with_',
        'jinja2.ext.autoescape',
    ]
)
env.install_gettext_callables(gettext, ngettext, newstyle=True)


def _error_page(**kwargs):
    """
    Custom error page to return plain text error message.
    """
    # Check expected response type.
    mtype = cherrypy.tools.accept.callable(
        ['text/html', 'text/plain', 'application/json'])  # @UndefinedVariable
    if mtype == 'text/plain':
        return kwargs.get('message')
    elif mtype == 'application/json':
        return {
            'message': kwargs.get('message', ''),
            'status': kwargs.get('status', '')
        }
    # Try to build a nice error page.
    try:
        env = cherrypy.request.config.get('tools.jinja2.env')
        extra_processor = cherrypy.request.config.get(
            'tools.jinja2.extra_processor')
        values = dict()
        if extra_processor:
            values.update(extra_processor(cherrypy.request))
        values.update(kwargs)
        template = env.get_template('error_page.html')
        return template.render(**values)
    except Exception:
        # If failing, send the raw error message.
        return kwargs.get('message')


@cherrypy.tools.db()
@cherrypy.tools.sessions()
@cherrypy.tools.formauth()
@cherrypy.tools.i18n(mo_dir=pkg_resources.resource_filename('cmdb', 'locales'), default='en_US', domain='messages')
@cherrypy.config(**{
    'error_page.default': _error_page,
    'tools.jinja2.env': env,
    'tools.jinja2.extra_processor': template_processor,
})
class Root(object):
    """
    Root entry point exposed using cherrypy.
    """

    def __init__(self, cfg):
        self.cfg = cfg
        cherrypy.config.update({
            'tools.sessions.storage_type': 'file' if cfg.session_dir else 'ram',
            'tools.sessions.storage_path': cfg.session_dir,
        })
        # Create SQL plugin
        plugin = cmdb.tools.db.SQLAlchemyPlugin(
            cherrypy.engine, Base, 'sqlite:////tmp/file.db')
        plugin.create()

        self.login = LoginPage()
        self.logout = LogoutPage()

    @cherrypy.expose
    @cherrypy.tools.jinja2(template='index.html')
    def index(self):
        return {}
