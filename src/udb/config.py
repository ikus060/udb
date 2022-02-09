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

import argparse
import sys

import cherrypy
import configargparse

# Get package version
try:
    import pkg_resources
    __version__ = pkg_resources.get_distribution("udb").version
except Exception:
    __version__ = 'DEV'


def parse_args(args=None, config_file_contents=None):
    """
    Load application configuration using program's arguments or environment variables.
    """
    args = sys.argv[1:] if args is None else args

    parser = configargparse.ArgumentParser(
        description='A web interface to manage IT network',
        add_env_var_help=True,
        auto_env_var_prefix='UDB_',)
    parser.add_argument(
        '-d', '--debug',
        action='store_true',
        help='enable debug mode - change the log level to DEBUG, print exception stack trace to the web interface')
    parser.add_argument(
        '-f', '--config', is_config_file=True, help='configuration file path')
    parser.add_argument(
        '-v', '--version', action='version', version='udb ' + __version__)
    parser.add_argument(
        '--server-host', metavar='IP',
        help='Define the IP address to listen to.', default='127.0.0.1')
    parser.add_argument(
        '--server-port', metavar='PORT',
        help='Define the port to listen to.', default='8080', type=int)
    parser.add_argument(
        '--log-file', metavar='FILE',
        help='Define the location of the log file.', default='')
    parser.add_argument(
        '--log-access-file', metavar='FILE',
        help='Define the location of the access log file.', default='')
    parser.add_argument(
        '--log-level', '--loglevel',
        help='Define the log level.',
        choices=['ERROR', 'WARN', 'INFO', 'DEBUG'],
        default='INFO')
    parser.add(
        '--session-dir', '--sessiondir',
        metavar='FOLDER',
        help='location where to store user session information. When undefined, the user sessions are kept in memory.')

    # Database
    parser.add(
        '--database-uri',
        metavar='URI',
        help="""Location of the database used for persistence. SQLite and PostgreSQL
            database are supported officially. To use a SQLite database you may
            define the location using a file path or a URI.
            e.g.: /srv/udb/file.db or sqlite:///srv/udb/file.db`.
            To use PostgreSQL server you must provide
            a URI similar to postgresql://user:pass@10.255.1.34/dbname and you
            must install required dependencies.
            By default, UDB uses a SQLite embedded database located at ./data.db""",
        default='sqlite:///data.db')

    parser.add(
        '--database-create-demo-data',
        action='store_true',
        help="""When this option is enabled, the application will create demonstration data."""
    )

    # Admin user
    parser.add_argument(
        '--admin-user', '--adminuser',
        metavar='USERNAME',
        help='administrator username. The administrator user get created on startup if the database is empty.',
        default='admin')

    parser.add_argument(
        '--admin-password',
        metavar='USERNAME',
        help="""administrator encrypted password as SSHA. Read online
            documentation to know more about how to encrypt your password
            into SSHA or use http://projects.marsching.org/weave4j/util/genpassword.php
            When defined, administrator password cannot be updated using the web interface.
            When undefined, default administrator password is `admin123` and
            it can be updated using the web interface.""")

    # LDAP
    parser.add_argument(
        '--ldap-add-missing-user', '--addmissinguser',
        action='store_true',
        help='enable creation of users from LDAP when the credential are valid.',
        default=False)

    parser.add_argument(
        '--ldap-add-user-default-role',
        help='default role used when creating users from LDAP. This parameter is only useful when `--ldap-add-missing-user` is enabled.',
        default='user',
        choices=['admin', 'user'])

    parser.add_argument(
        '--ldap-uri', '--ldapuri',
        help='URL to the LDAP server used to validate user credentials. e.g.: ldap://localhost:389')

    parser.add_argument(
        '--ldap-base-dn', '--ldapbasedn',
        metavar='DN',
        help='DN of the branch of the directory where all searches should start from. e.g.: dc=my,dc=domain',
        default="")

    parser.add_argument(
        '--ldap-scope', '--ldapscope',
        help='scope of the search. Can be either base, onelevel or subtree',
        choices=['base', 'onelevel', 'subtree'],
        default="subtree")

    parser.add_argument(
        '--ldap-tls', '--ldaptls',
        action='store_true',
        help='enable TLS')

    parser.add_argument(
        '--ldap-username-attribute', '--ldapattribute',
        metavar='ATTRIBUTE',
        help="The attribute to search username. If no attributes are provided, the default is to use `uid`. It's a good idea to choose an attribute that will be unique across all entries in the subtree you will be using.",
        default='uid')

    parser.add_argument(
        '--ldap-filter', '--ldapfilter',
        help="search filter to limit LDAP lookup. If not provided, defaults to (objectClass=*), which searches for all objects in the tree.",
        default='(objectClass=*)')

    parser.add_argument(
        '--ldap-required-group', '--ldaprequiredgroup',
        metavar='GROUPNAME',
        help="name of the group of which the user must be a member to access rdiffweb. Should be used with ldap-group-attribute and ldap-group-attribute-is-dn.")

    parser.add_argument(
        '--ldap-group-attribute', '--ldapgroupattribute',
        metavar='ATTRIBUTE',
        help="name of the attribute defining the groups of which the user is a member. Should be used with ldap-required-group and ldap-group-attribute-is-dn.",
        default='member')

    parser.add_argument(
        '--ldap-group-attribute-is-dn', '--ldapgroupattributeisdn',
        help="True if the content of the attribute `ldap-group-attribute` is a DN.",
        action='store_true')

    parser.add_argument(
        '--ldap-bind-dn', '--ldapbinddn',
        metavar='DN',
        help="optional DN used to bind to the server when searching for entries. If not provided, will use an anonymous bind.",
        default="")

    parser.add_argument(
        '--ldap-bind-password', '--ldapbindpassword',
        metavar='PASSWORD',
        help="password to use in conjunction with LdapBindDn. Note that the bind password is probably sensitive data, and should be properly protected. You should only use the LdapBindDn and LdapBindPassword if you absolutely need them to search the directory.",
        default="")

    parser.add_argument(
        '--ldap-version', '--ldapversion', '--ldapprotocolversion',
        help="version of LDAP in use either 2 or 3. Default to 3.",
        default=3,
        type=int,
        choices=[2, 3])

    parser.add_argument(
        '--ldap-network-timeout', '--ldapnetworktimeout',
        metavar='SECONDS',
        help="timeout in seconds value used for LDAP connection",
        default=100,
        type=int)

    parser.add_argument(
        '--ldap-timeout', '--ldaptimeout',
        metavar='SECONDS',
        help="timeout in seconds value used for LDAP request",
        default=300,
        type=int)

    parser.add_argument(
        '--ldap-encoding', '--ldapencoding',
        metavar='ENCODING',
        help="encoding used by your LDAP server.",
        default="utf-8")

    parser.add_argument(
        '--ldap-check-shadow-expire', '--ldapcheckshadowexpire',
        help="enable validation of shadow expired when validating user's credential. User will not be allowed to login if the account expired.",
        default=False,
        action='store_true')

    # Branding
    parser.add_argument(
        '--header-name', metavar='NAME', default='Universal Database',
        help='Name used in the title for this application.')
    parser.add_argument(
        '--footer-name', metavar='NAME', default='IKUS Soft UDB',
        help='Text displayed in the footer along "power by".')
    parser.add_argument(
        '--footer-url', metavar='URL', default="https://gitlab.com/ikus-soft/udb",
        help='URL used in the footer along "power by".')

    # Here we append a list of arguments for each locale.
    flags = (['--welcome-msg']
             + ['--welcome-msg-' + i for i in ['ca', 'en', 'es', 'fr', 'ru']]
             + ['--welcomemsg'])
    parser.add_argument(
        *flags,
        metavar='HTML',
        help='replace the welcome message displayed in the login page for default locale or for a specific locale',
        action=LocaleAction)

    return parser.parse_args(args, config_file_contents=config_file_contents)


class LocaleAction(argparse.Action):
    """
    Custom Action to support defining arguments with locale.
    """

    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        super(LocaleAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, value, option_string=None):
        if option_string[-3] == '-':
            # When using arguments, we can extract the locale from the argument key
            locale = option_string[-2:]
        elif value[2] == ':':
            # When using config file, the locale could be extract from the value e.g. fr:message
            locale = value[0:2]
            value = value[3:]
        else:
            locale = ''
        # Create a dictionary with locale.
        items = getattr(namespace, self.dest) or {}
        items[locale] = value
        setattr(namespace, self.dest, items)


class Option(object):

    def __init__(self, key):
        assert key
        self.key = key

    def __get__(self, instance, owner):
        """
        Return a property to wrap the given option.
        """
        return self.get(instance)

    def get(self, instance=None):
        """
        Return the value of this options.
        """
        app = cherrypy.tree.apps[''].root or getattr(instance, 'app', None)
        assert app, "Option() can't get reference to app"
        assert app.cfg, "Option() can't get reference to app.cfg"
        return getattr(app.cfg, self.key)