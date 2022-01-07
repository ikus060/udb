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

import logging

import cherrypy
import jinja2
import pkg_resources

import udb.tools.auth_form  # noqa: import cherrypy.tools.auth_form
import udb.tools.auth_basic  # noqa: import cherrypy.tools.auth_basic
import udb.tools.currentuser  # noqa: import cherrypy.tools.currentuser
import udb.tools.db  # noqa: import cherrypy.tools.db
import udb.tools.jinja2  # noqa: import cherrypy.tools.jinja2
from udb.controller import lastupdated, template_processor
from udb.controller.api import Api
from udb.controller.login import LoginPage
from udb.controller.logout import LogoutPage
from udb.controller.network import (DhcpRecordApi, DhcpRecordPage,
                                    DnsRecordApi, DnsRecordPage, DnsZoneApi,
                                    DnsZonePage, SubnetApi, SubnetPage)
from udb.controller.static import Static
from udb.core.model import DhcpRecord, DnsRecord, DnsZone, Subnet, User
from udb.tools.i18n import gettext, ngettext

logger = logging.getLogger(__name__)


#
# Create singleton Jinja2 environement.
#
env = jinja2.Environment(
    loader=jinja2.PackageLoader('udb'),
    auto_reload=True,
    autoescape=True,
    extensions=[
        'jinja2.ext.i18n',
        'jinja2.ext.with_',
        'jinja2.ext.autoescape',
    ]
)
env.install_gettext_callables(gettext, ngettext, newstyle=True)
env.filters['lastupdated'] = lastupdated


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
@cherrypy.tools.auth_form()
@cherrypy.tools.currentuser()
@cherrypy.tools.i18n(mo_dir=pkg_resources.resource_filename('udb', 'locales'), default='en_US', domain='messages')
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
        # Create database if required
        cherrypy.tools.db.create_all()
        # Create default admin if missing
        created = User.create_default_admin(cfg.admin_user, cfg.admin_password)
        if created:
            # TODO Add more stuff for developement
            User(username='patrik', fullname='Patrik Dufresne').add()
            User(username='daniel', fullname='Daniel Baumann').add()
            DnsZone(name='bfh.ch', notes='This is a note').add()
            DnsZone(name='bfh.science', notes='This is a note').add()
            DnsZone(name='bfh.info', notes='This is a note').add()

            # Subnet
            Subnet(ip_cidr='147.87.0.0/16',
                   name='its-main-4',
                   vrf=1, notes='main').add()
            Subnet(ip_cidr='2002::1234:abcd:ffff:c0a8:101/64',
                   name='its-main-6',
                   vrf=1, notes='main').add()
            Subnet(ip_cidr='147.87.250.0/24',
                   name='DMZ',
                   vrf=1, notes='public').add()
            Subnet(ip_cidr='147.87.208.0/24',
                   name='ARZ',
                   vrf=1, notes='BE.net').add()

            # DHCP
            DhcpRecord(ip='147.87.250.1', mac='00:ba:d5:a2:34:56',
                       notes='webserver bla bla bla').add()

            # DNS
            DnsRecord(name='foo.bfh.ch',
                      type='A',
                      value='147.87.250.0').add()
            DnsRecord(name='bar.bfh.ch',
                      type='A',
                      value='147.87.250.1').add()
            DnsRecord(name='bar.bfh.ch',
                      type='CNAME',
                      value='www.bar.bfh.ch').add()
            DnsRecord(name='baz.bfh.ch',
                      type='A',
                      value='147.87.250.2').add()

        User.session.commit()
        self.login = LoginPage()
        self.logout = LogoutPage()
        self.static = Static()
        self.api = Api()
        # Import modules to be added to this app.
        self.dnszone = DnsZonePage()
        self.api.dnszone = DnsZoneApi()
        self.subnet = SubnetPage()
        self.api.subnet = SubnetApi()
        self.dnsrecord = DnsRecordPage()
        self.api.dnsrecord = DnsRecordApi()
        self.dhcprecord = DhcpRecordPage()
        self.api.dhcprecord = DhcpRecordApi()

    @cherrypy.expose
    @cherrypy.tools.jinja2(template='index.html')
    def index(self):
        return {}
