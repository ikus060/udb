# udb, A web interface to manage IT network
# Copyright (C) 2022-2026 IKUS Software inc.
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
import cherrypy_foundation.plugins.db  # noqa: import cherrypy.db
import cherrypy_foundation.plugins.ldap  # noqa
import cherrypy_foundation.plugins.restapi
import cherrypy_foundation.plugins.scheduler  # noqa
import cherrypy_foundation.plugins.smtp  # noqa
import cherrypy_foundation.tools.auth  # noqa: import cherrypy.tools.auth
import cherrypy_foundation.tools.auth_mfa  # noqa: import cherrypy.tools.auth_mfa

# import cherrypy_foundation.tools.errors  # noqa
import cherrypy_foundation.tools.jinja2  # noqa: import cherrypy.tools.jinja2
import cherrypy_foundation.tools.ratelimit
import cherrypy_foundation.tools.secure_headers  # noqa: import cherrypy.tools.secure_headers
import ujson
from cherrypy import Application
from cherrypy_foundation.error_page import error_page
from cherrypy_foundation.flash import get_flashed_messages

import udb.core.notification  # noqa
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
from udb.controller.language import Language
from udb.controller.load_page import LoadPage
from udb.controller.login_page import LoginPage, LogoutPage
from udb.controller.mac_page import MacPage
from udb.controller.mfa_page import MfaPage
from udb.controller.notifications_page import NotificationsPage
from udb.controller.profile_page import ProfilePage
from udb.controller.rule_page import RuleApi, RulePage
from udb.controller.search_page import SearchPage
from udb.controller.static import Static
from udb.controller.subnet_page import SubnetPage
from udb.controller.user_page import UserPage
from udb.controller.vrf_page import VrfPage
from udb.core.model import DhcpRecord, DnsRecord, DnsZone, Subnet, User, Vrf

SESSION_USER_KEY = 'username'

# Define cherrypy development environment
cherrypy.config.environments['development'] = {
    'engine.autoreload.on': True,
    'checker.on': False,
    'tools.log_headers.on': True,
    'request.show_tracebacks': True,
    'request.show_mismatched_params': True,
    'log.screen': False,
}


def json_handler(*args, **kwargs):
    """
    Custom Json Handler to produce a more compact Json using ujson.
    """
    value = cherrypy.serving.request._json_inner_handler(*args, **kwargs)
    return ujson.dumps(value).encode('utf-8')


@cherrypy.tools.auth(
    session_user_key=SESSION_USER_KEY,
    user_lookup_func=User.get_create_or_update_user,
    user_from_key_func=User.query_user,
    checkpassword=[User.authenticate, cherrypy.ldap.authenticate],
)
@cherrypy.tools.auth_mfa(mfa_enabled=lambda: cherrypy.request.currentuser.mfa)
@cherrypy.tools.i18n(
    lang=lambda: getattr(cherrypy.request, 'currentuser', False) and cherrypy.request.currentuser.lang,
    tzinfo=lambda: getattr(cherrypy.serving.request, 'currentuser', False) and cherrypy.request.currentuser.timezone,
)
@cherrypy.tools.proxy(local=None, remote='X-Real-IP')
@cherrypy.tools.ratelimit(on=False, session_user_key=SESSION_USER_KEY)
@cherrypy.tools.secure_headers(
    csp={
        "default-src": "'self'",
        "script-src": ("'self'", "'unsafe-inline'"),
        "style-src": ("'self'", "'unsafe-inline'"),
        "img-src": ("'self'", "data:"),
    }
)
@cherrypy.tools.sessions()
@cherrypy.tools.sessions_timeout()
class Root(object):
    """
    Root entry point exposed using cherrypy.
    """

    def __init__(self):
        self.api = Api()
        self.audit = AuditPage()
        self.dashboard = DashboardPage()
        self.login = LoginPage()
        self.logout = LogoutPage()
        self.notifications = NotificationsPage()
        self.profile = ProfilePage()
        self.search = SearchPage()
        self.load = LoadPage()
        self.static = Static()
        self.language = Language()
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
        self.mfa = MfaPage()
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

    @cherrypy.expose
    @cherrypy.tools.jinja2(template='index.html')
    def index(self):
        raise cherrypy.HTTPRedirect(url_for('dashboard', ''))


class UdbApplication(Application):
    def __init__(self, cfg):
        self.cfg = cfg

        # Configure Jinja2 environment.
        env = cherrypy.tools.jinja2.create_env(
            package_name='udb',
            globals={
                'footer_name': cfg.footer_name,
                'footer_url': cfg.footer_url,
                'get_flashed_messages': get_flashed_messages,
                'header_name': cfg.header_name,
                'url_for': url_for,
                'version': udb.__version__,
            },
        )

        # Pick the right implementation for storage
        rate_limit_storage_class = cherrypy_foundation.tools.ratelimit.RamRateLimit
        session_storage_class = cherrypy.lib.sessions.RamSession
        if cfg.session_dir:
            rate_limit_storage_class = cherrypy_foundation.tools.ratelimit.FileRateLimit
            session_storage_class = cherrypy.lib.sessions.FileSession
        cherrypy.config.update(
            {
                # Define cherrypy config based on debug flag.
                'environment': 'development' if cfg.debug else 'production',
                # Define error page handler.
                'error_page.default': error_page,
                # Configure database plugins
                'db.uri': cfg.database_uri,
                'db.debug': cfg.debug,
                # Configure external_url
                'tools.proxy.base': cfg.external_url,
                # Configure session storage
                'tools.sessions.debug': cfg.debug,
                'tools.sessions.storage_class': session_storage_class,
                'tools.sessions.storage_path': cfg.session_dir,
                'tools.sessions.httponly': True,
                'tools.sessions.timeout': cfg.session_idle_timeout,  # minutes
                'tools.sessions.persistent': False,  # auth_form should update this.
                'tools.sessions_timeout.persistent_timeout': cfg.session_persistent_timeout,  # minutes
                'tools.sessions_timeout.absolute_timeout': cfg.session_absolute_timeout,  # minutes
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
                # Configure notification
                'notification.env': env,
                'notification.header_name': cfg.header_name,
                'notification.catch_all_email': cfg.notification_catch_all_email,
                # Configure locales
                'tools.i18n.default': cfg.default_lang,
                'tools.i18n.default_timezone': cfg.default_timezone,
                'tools.i18n.mo_dir': importlib.resources.files('udb') / 'locales',
                'tools.i18n.domain': 'messages',
            }
        )

        config = {
            '/api': {'request.dispatch': cherrypy_foundation.plugins.restapi.Dispatcher()},
        }

        # Initialize the application
        Application.__init__(self, root=Root(), config=config)

        # Register a late callback to create admin user when starting
        cherrypy.engine.subscribe('start', self.on_start, priority=250)

    def on_start(self):
        # Since we are not a real plugin, let unsubscribe to avoid interference if server get restarted.
        cherrypy.engine.unsubscribe('start', self.on_start)

        # Create database if required
        cherrypy.db.create_all()

        # Create default admin if missing
        user = User.create_default_admin(self.cfg.admin_user, self.cfg.admin_password)
        if user:
            user.commit()
