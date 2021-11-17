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
import pkg_resources

import cmdb.db  # noqa
import cmdb.jinja2  # noqa
import jinja2
from cmdb.i18n import gettext, ngettext
from cmdb.model import Base, User

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

#
# Create singleton SQLAlchemyPlugin
#
cmdb.db.SQLAlchemyPlugin(cherrypy.engine, Base,
                         'sqlite:////tmp/file.db').create()


@cherrypy.tools.db()
@cherrypy.tools.i18n(mo_dir=pkg_resources.resource_filename('cmdb', 'locales'), default='en_US', domain='messages')
@cherrypy.config(**{'tools.jinja2.env': env})
class Root(object):
    """
    Root entry point exposed using cherrypy.
    """

    def __init__(self, cfg):
        self.cfg = cfg

    def render_template(self, name, **kwargs):
        tmpl = self.env.get_template('index.html')
        return tmpl.render(
            header_name=self.cfg.header_name,
            footer_url=self.cfg.footer_url,
            footer_name=self.cfg.footer_name,
            **kwargs)

    @cherrypy.expose
    @cherrypy.tools.jinja2(template='index.html')
    def index(self):
        db = cherrypy.request.db
        # Add user
        ed_user = User(
            name='ed')
        db.add(ed_user)
        # List user
        users = list(db.query(User))
        return {'users': users}
