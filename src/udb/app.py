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
import jinja2
import pkg_resources

import udb.core.login  # noqa
import udb.core.notification  # noqa
import udb.plugins.ldap  # noqa
import udb.plugins.smtp  # noqa
import udb.tools.auth_basic  # noqa: import cherrypy.tools.auth_basic
import udb.tools.auth_form  # noqa: import cherrypy.tools.auth_form
import udb.tools.currentuser  # noqa: import cherrypy.tools.currentuser
import udb.tools.db  # noqa: import cherrypy.tools.db
import udb.tools.errors  # noqa
import udb.tools.jinja2  # noqa: import cherrypy.tools.jinja2
from udb.controller import lastupdated, template_processor, url_for
from udb.controller.api import Api
from udb.controller.common_page import CommonApi, CommonPage
from udb.controller.login_page import LoginPage
from udb.controller.logout_page import LogoutPage
from udb.controller.network_page import DhcpRecordForm, DnsRecordForm, DnsZoneForm, IpForm, SubnetForm
from udb.controller.notifications_page import NotificationsPage
from udb.controller.profile_page import ProfilePage
from udb.controller.search_page import SearchPage
from udb.controller.static import Static
from udb.controller.user_page import UserForm
from udb.core.model import DhcpRecord, DnsRecord, DnsZone, Ip, Subnet, User
from udb.tools.i18n import gettext, ngettext

#
# Create singleton Jinja2 environement.
#
env = jinja2.Environment(
    loader=jinja2.PackageLoader('udb'),
    auto_reload=True,
    autoescape=True,
    extensions=[
        'jinja2.ext.i18n',
    ],
)
env.install_gettext_callables(gettext, ngettext, newstyle=True)
env.filters['lastupdated'] = lastupdated
env.globals['url_for'] = url_for


def _error_page(**kwargs):
    """
    Custom error page to return plain text error message.
    """
    # Check expected response type.
    mtype = cherrypy.tools.accept.callable(['text/html', 'text/plain', 'application/json'])  # @UndefinedVariable
    if mtype == 'text/plain':
        return kwargs.get('message')
    elif mtype == 'application/json':
        return {'message': kwargs.get('message', ''), 'status': kwargs.get('status', '')}
    # Try to build a nice error page.
    try:
        env = cherrypy.request.config.get('tools.jinja2.env')
        extra_processor = cherrypy.request.config.get('tools.jinja2.extra_processor')
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
@cherrypy.tools.currentuser(userobj=lambda username: User.query.filter_by(username=username).first())
@cherrypy.tools.i18n(mo_dir=pkg_resources.resource_filename('udb', 'locales'), default='en_US', domain='messages')
class Root(object):
    """
    Root entry point exposed using cherrypy.
    """

    def __init__(self, cfg):
        self.cfg = cfg
        cherrypy.config.update(
            {
                'error_page.default': _error_page,
                # Configure database plugins
                'tools.db.uri': cfg.database_uri,
                'tools.db.debug': cfg.debug,
                # Configure session storage
                'tools.sessions.storage_type': 'file' if cfg.session_dir else 'ram',
                'tools.sessions.storage_path': cfg.session_dir,
                # Configure jinja2 templating engine
                'tools.jinja2.env': env,
                'tools.jinja2.extra_processor': template_processor,
                # Configure LDAP plugin
                'ldap.uri': cfg.ldap_uri,
                'ldap.base_dn': cfg.ldap_base_dn,
                'ldap.bind_dn': cfg.ldap_bind_dn,
                'ldap.bind_password': cfg.ldap_bind_password,
                'ldap.scope': cfg.ldap_scope,
                'ldap.tls': cfg.ldap_tls,
                'ldap.username_attribute': cfg.ldap_username_attribute,
                'ldap.required_group': cfg.ldap_required_group,
                'ldap.group_attribute': cfg.ldap_group_attribute,
                'ldap.group_attribute_is_dn': cfg.ldap_group_attribute_is_dn,
                'ldap.version': cfg.ldap_version,
                'ldap.network_timeout': cfg.ldap_network_timeout,
                'ldap.timeout': cfg.ldap_timeout,
                'ldap.encoding': cfg.ldap_encoding,
                'ldap.check_shadow_expire': cfg.ldap_check_shadow_expire,
                'ldap.fullname_attribute': cfg.ldap_fullname_attribute,
                'ldap.firstname_attribute': cfg.ldap_firstname_attribute,
                'ldap.lastname_attribute': cfg.ldap_lastname_attribute,
                'ldap.email_attribute': cfg.ldap_email_attribute,
                # Configure SMTP plugin
                'smtp.server': cfg.smtp_server,
                'smtp.username': cfg.smtp_username,
                'smtp.password': cfg.smtp_password,
                'smtp.email_from': cfg.smtp_from and '%s <%s>' % (cfg.header_name, cfg.smtp_from),
                'smtp.encryption': cfg.smtp_encryption,
                # Configure login
                'login.add_missing_user': cfg.add_missing_user,
                'login.add_user_default_role': User.coerce_role_name(cfg.add_user_default_role),
                # Configure notification
                'notification.env': env,
                'notification.header_name': cfg.header_name,
                'notification.catch_all_email': cfg.notification_catch_all_email,
            }
        )
        # Create database if required
        cherrypy.tools.db.create_all()
        # Create default admin if missing
        created = User.create_default_admin(cfg.admin_user, cfg.admin_password)
        if created and cfg.database_create_demo_data:
            User.create(username='guest', fullname='Default Guest', password='guest', role=User.ROLE_GUEST)
            User.create(username='user', fullname='Default User', password='user', role=User.ROLE_USER)

            # Subnet
            subnet = Subnet(ip_cidr='147.87.250.0/24', name='DMZ', vrf=1, notes='public').add()
            Subnet(ip_cidr='147.87.0.0/16', name='its-main-4', vrf=1, notes='main').add()
            Subnet(ip_cidr='2002::1234:abcd:ffff:c0a8:101/64', name='its-main-6', vrf=1, notes='main').add()
            Subnet(ip_cidr='147.87.208.0/24', name='ARZ', vrf=1, notes='BE.net').add()

            DnsZone(name='bfh.ch', notes='This is a note', subnets=[subnet]).add()
            DnsZone(name='bfh.science', notes='This is a note').add()
            DnsZone(name='bfh.info', notes='This is a note').add()

            # DHCP
            DhcpRecord(ip='147.87.250.1', mac='00:ba:d5:a2:34:56', notes='webserver bla bla bla').add()

            # DNS
            DnsRecord(name='foo.bfh.ch', type='A', value='147.87.250.0').add()
            DnsRecord(name='bar.bfh.ch', type='A', value='147.87.250.1').add()
            DnsRecord(name='bar.bfh.ch', type='CNAME', value='www.bar.bfh.ch').add()
            DnsRecord(name='baz.bfh.ch', type='A', value='147.87.250.2').add()

        User.session.commit()
        self.api = Api()
        self.login = LoginPage()
        self.logout = LogoutPage()
        self.notifications = NotificationsPage()
        self.profile = ProfilePage()
        self.search = SearchPage()
        self.static = Static()
        # Import modules to be added to this app.
        self.dnszone = CommonPage(DnsZone, DnsZoneForm)
        self.subnet = CommonPage(Subnet, SubnetForm)
        self.dnsrecord = CommonPage(DnsRecord, DnsRecordForm)
        self.dhcprecord = CommonPage(DhcpRecord, DhcpRecordForm)
        self.ip = CommonPage(Ip, IpForm, has_new=False)
        self.user = CommonPage(User, UserForm, list_role=User.ROLE_ADMIN, edit_role=User.ROLE_ADMIN)
        # Api
        self.api.dnszone = CommonApi(DnsZone)
        self.api.subnet = CommonApi(Subnet)
        self.api.dnsrecord = CommonApi(DnsRecord)
        self.api.dhcprecord = CommonApi(DhcpRecord)

    @cherrypy.expose
    @cherrypy.tools.jinja2(template='index.html')
    def index(self):
        return {}
