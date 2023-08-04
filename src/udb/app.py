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
import ujson

import udb.core.login  # noqa
import udb.core.notification  # noqa
import udb.plugins.ldap  # noqa
import udb.plugins.smtp  # noqa
import udb.tools.auth_form  # noqa: import cherrypy.tools.auth_form
import udb.tools.currentuser  # noqa: import cherrypy.tools.currentuser
import udb.tools.db  # noqa: import cherrypy.tools.db
import udb.tools.errors  # noqa
import udb.tools.jinja2  # noqa: import cherrypy.tools.jinja2
import udb.tools.ratelimit
import udb.tools.secure_headers  # noqa: import cherrypy.tools.secure_headers
from udb.controller import template_processor, url_for
from udb.controller.api import Api
from udb.controller.audit_page import AuditPage
from udb.controller.common_page import CommonApi
from udb.controller.dashboard_page import DashboardPage
from udb.controller.deployment_page import DeploymentApi, DeploymentPage
from udb.controller.dhcprecord_page import DhcpRecordPage
from udb.controller.dnsrecord_page import DnsRecordPage
from udb.controller.dnszone_page import DnsZonePage
from udb.controller.environment_page import EnvironmentApi, EnvironmentPage
from udb.controller.ip_page import IpPage
from udb.controller.load_page import LoadPage
from udb.controller.login_page import LoginPage
from udb.controller.mac_page import MacPage
from udb.controller.notifications_page import NotificationsPage
from udb.controller.profile_page import ProfilePage
from udb.controller.rule_page import RuleApi, RulePage
from udb.controller.search_page import SearchPage
from udb.controller.static import Static
from udb.controller.subnet_page import SubnetPage
from udb.controller.user_page import UserPage
from udb.controller.vrf_page import VrfPage
from udb.core.model import DhcpRecord, DnsRecord, DnsZone, Subnet, User, Vrf
from udb.tools.i18n import format_datetime, gettext_lazy, ngettext

# Define cherrypy development environment
cherrypy.config.environments['development'] = {
    'engine.autoreload.on': True,
    'checker.on': False,
    'tools.log_headers.on': True,
    'request.show_tracebacks': True,
    'request.show_mismatched_params': True,
    'log.screen': False,
}

#
# Create singleton Jinja2 environement.
#
env = jinja2.Environment(
    loader=jinja2.PackageLoader('udb'),
    auto_reload=True,
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
    extensions=[
        'jinja2.ext.i18n',
    ],
)
env.install_gettext_callables(gettext_lazy, ngettext, newstyle=True)
env.globals['url_for'] = url_for
env.filters['format_datetime'] = format_datetime


def _error_page(**kwargs):
    """
    Custom error page to return plain text error message.
    """
    # Check expected response type.
    mtype = cherrypy.serving.response.headers.get('Content-Type') or cherrypy.tools.accept.callable(
        ['text/html', 'text/plain', 'application/json']
    )

    # Replace message by generic one for 404 to avoid vulnerability.
    if kwargs.get('status', '') == '404 Not Found':
        kwargs['message'] = 'Nothing matches the given URI'

    if mtype == 'text/plain':
        return kwargs.get('message')
    elif mtype == 'application/json':
        return ujson.dumps({'message': kwargs.get('message', ''), 'status': kwargs.get('status', '')})
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


def json_handler(*args, **kwargs):
    """
    Custom Json Handler to produce a more compact Json.
    """
    value = cherrypy.serving.request._json_inner_handler(*args, **kwargs)
    return ujson.dumps(value).encode('utf-8')


@cherrypy.tools.db()
@cherrypy.tools.proxy(local=None, remote='X-Real-IP')
@cherrypy.tools.sessions()
@cherrypy.tools.auth_form()
@cherrypy.tools.currentuser(userobj=User.query_user)
@cherrypy.tools.i18n(func=lambda: getattr(cherrypy.request, 'currentuser', False) and cherrypy.request.currentuser.lang)
@cherrypy.tools.secure_headers(
    csp="default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net/; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net/; img-src 'self' data: https://cdn.jsdelivr.net/;font-src https://cdn.jsdelivr.net/"
)
class Root(object):
    """
    Root entry point exposed using cherrypy.
    """

    def __init__(self, cfg):
        self.cfg = cfg
        # Pick the right implementation for storage
        rate_limit_storage_class = udb.tools.ratelimit.RamRateLimit
        session_storage_class = cherrypy.lib.sessions.RamSession
        if cfg.session_dir:
            rate_limit_storage_class = udb.tools.ratelimit.FileRateLimit
            session_storage_class = cherrypy.lib.sessions.FileSession
        cherrypy.config.update(
            {
                # Define cherrypy config based on debug flag.
                'environment': 'development' if cfg.debug else 'production',
                # Define error page handler.
                'error_page.default': _error_page,
                # Configure database plugins
                'tools.db.uri': cfg.database_uri,
                'tools.db.debug': cfg.debug,
                # Configure session storage
                'tools.sessions.storage_class': session_storage_class,
                'tools.sessions.storage_path': cfg.session_dir,
                # Configure rate limit
                'tools.ratelimit.debug': cfg.debug,
                'tools.ratelimit.limit': cfg.rate_limit,
                'tools.ratelimit.storage_class': rate_limit_storage_class,
                'tools.ratelimit.storage_path': cfg.session_dir,
                # Configure jinja2 templating engine
                'tools.jinja2.env': env,
                'tools.jinja2.extra_processor': template_processor,
                # Configure json_handler
                'tools.json_out.handler': json_handler,
                # Configure LDAP plugin
                'ldap.uri': cfg.ldap_uri,
                'ldap.base_dn': cfg.ldap_base_dn,
                'ldap.bind_dn': cfg.ldap_bind_dn,
                'ldap.bind_password': cfg.ldap_bind_password,
                'ldap.scope': cfg.ldap_scope,
                'ldap.tls': cfg.ldap_tls,
                'ldap.username_attribute': cfg.ldap_username_attribute,
                'ldap.user_filter': cfg.ldap_user_filter,
                'ldap.required_group': cfg.ldap_admin_group
                + cfg.ldap_dnszone_mgmt_group
                + cfg.ldap_subnet_mgmt_group
                + cfg.ldap_user_group
                + cfg.ldap_guest_group,
                'ldap.group_filter': cfg.ldap_group_filter,
                'ldap.group_attribute': cfg.ldap_group_attribute,
                'ldap.group_attribute_is_dn': cfg.ldap_group_attribute_is_dn,
                'ldap.version': cfg.ldap_version,
                'ldap.network_timeout': cfg.ldap_network_timeout,
                'ldap.timeout': cfg.ldap_timeout,
                'ldap.encoding': cfg.ldap_encoding,
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
                'login.query_user': User.query_user,
                'login.add_missing_user': cfg.add_missing_user,
                'login.add_user_default_role': cfg.add_user_default_role,
                'login.admin_group': cfg.ldap_admin_group,
                'login.dnszone_mgmt_group': cfg.ldap_dnszone_mgmt_group,
                'login.subnet_mgmt_group': cfg.ldap_subnet_mgmt_group,
                'login.user_group': cfg.ldap_user_group,
                'login.guest_group': cfg.ldap_guest_group,
                # Configure notification
                'notification.env': env,
                'notification.header_name': cfg.header_name,
                'notification.catch_all_email': cfg.notification_catch_all_email,
                # Configure locales
                'tools.i18n.default': cfg.default_lang,
                'tools.i18n.default_timezone': cfg.default_timezone,
                'tools.i18n.mo_dir': pkg_resources.resource_filename('udb', 'locales'),
                'tools.i18n.domain': 'messages',
            }
        )
        # Create database if required
        cherrypy.tools.db.create_all()
        # Create default admin if missing
        User.create_default_admin(cfg.admin_user, cfg.admin_password)

        # Commit changes to database.
        cherrypy.tools.db.get_session().commit()
        self.api = Api()
        self.audit = AuditPage()
        self.dashboard = DashboardPage()
        self.login = LoginPage()
        self.notifications = NotificationsPage()
        self.profile = ProfilePage()
        self.search = SearchPage()
        self.load = LoadPage()
        self.static = Static()
        # Import modules to be added to this app.
        self.vrf = VrfPage()
        self.rule = RulePage()
        self.dnszone = DnsZonePage()
        self.subnet = SubnetPage()
        self.dnsrecord = DnsRecordPage()
        self.dhcprecord = DhcpRecordPage()
        self.ip = IpPage()
        self.user = UserPage()
        self.mac = MacPage()
        self.environment = EnvironmentPage()
        self.deployment = DeploymentPage()
        # Api
        self.api.dnszone = CommonApi(DnsZone, new_perm=User.PERM_DNSZONE_CREATE)
        self.api.subnet = CommonApi(Subnet, new_perm=User.PERM_SUBNET_CREATE)
        self.api.dnsrecord = CommonApi(DnsRecord)
        self.api.dhcprecord = CommonApi(DhcpRecord)
        self.api.vrf = CommonApi(Vrf)
        self.api.deployment = DeploymentApi()
        self.api.environment = EnvironmentApi()
        self.api.rule = RuleApi()
        # Configure logos
        self.static.header_logo = cherrypy.tools.staticfile.handler(
            filename=cfg.header_logo
            if cfg.header_logo
            else pkg_resources.resource_filename('udb.controller.static', 'udb-logo.png')
        )
        self.static.favicon = cherrypy.tools.staticfile.handler(
            filename=cfg.favicon
            if cfg.favicon
            else pkg_resources.resource_filename('udb.controller.static', 'udb_16.svg')
        )

    @cherrypy.expose
    @cherrypy.tools.jinja2(template='index.html')
    def index(self):
        raise cherrypy.HTTPRedirect(url_for('dashboard', ''))
