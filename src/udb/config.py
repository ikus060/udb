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

import argparse
import grp
import pwd
import sys

import cherrypy
import configargparse

from udb.tools.i18n import gettext as _

# Get package version
try:
    import pkg_resources

    __version__ = pkg_resources.get_distribution("udb").version
except Exception:
    __version__ = 'DEV'


def _userid(value):
    """
    Parse the user value attribute that could be either a username or a userid.
    """
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return pwd.getpwnam(value).pw_uid
    except KeyError:
        raise argparse.ArgumentError('user %s not found' % value)


def _groupid(value):
    """
    Parse the group value that could be either a group name or groupid.
    """
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return grp.getgrnam(value).gr_gid
    except KeyError:
        raise argparse.ArgumentError('group %s not found' % value)


def _umask(value):
    """
    Validate the umask value. Read it as octal and return integer.
    """
    try:
        return int(value, base=8)
    except ValueError:
        raise argparse.ArgumentError('invalid umask value %s' % value)


def parse_args(args=None, config_file_contents=None):
    """
    Load application configuration using program's arguments or environment variables.
    """
    args = sys.argv[1:] if args is None else args

    parser = configargparse.ArgumentParser(
        description='A web interface to manage IT network',
        default_config_files=['/etc/udb/udb.conf', '/etc/udb/udb.conf.d/*.conf'],
        add_env_var_help=True,
        auto_env_var_prefix='UDB_',
    )
    parser.add_argument(
        '-d',
        '--debug',
        action='store_true',
        help=_('enable debug mode - change the log level to DEBUG, print exception stack trace to the web interface'),
    )
    parser.add_argument('-f', '--config', is_config_file=True, help=_('configuration file path'))
    parser.add_argument('-v', '--version', action='version', version='udb ' + __version__)
    parser.add_argument(
        '--server-host', metavar='IP', help=_('Define the IP address to listen to.'), default='127.0.0.1'
    )
    parser.add_argument(
        '--server-port', metavar='PORT', help=_('Define the port to listen to.'), default='8080', type=int
    )
    parser.add(
        '--external-url',
        metavar='URL',
        help='URL that should be used to reach this service. You can use the IP of your server, but a Fully Qualified Domain Name (FQDN) is preferred.',
    )
    parser.add_argument('--log-file', metavar='FILE', help=_('Define the location of the log file.'), default='')
    parser.add_argument(
        '--log-access-file', metavar='FILE', help=_('Define the location of the access log file.'), default=''
    )
    parser.add_argument(
        '--log-level',
        '--loglevel',
        help=_('Define the log level.'),
        choices=['ERROR', 'WARN', 'INFO', 'DEBUG'],
        default='INFO',
    )
    parser.add(
        '--session-dir',
        '--sessiondir',
        '--rate-limit-dir',
        metavar='FOLDER',
        help=_(
            'location where to store user session information and rate-limit information. When undefined, the data are kept in memory.'
        ),
    )

    parser.add_argument(
        '--default-lang',
        help='default application locale. e.g.: `fr`',
        default='en_US',
    )

    parser.add(
        '--rate-limit',
        metavar='LIMIT',
        type=int,
        default=20,
        help=_(
            'maximum number of requests per hours that can be made on sensitive endpoint. When this limit is reached, an HTTP 429 message is returned to the user or user get logged out. This security measure is used to limit brute force attacks on the login page and the RESTful API.'
        ),
    )

    # Database
    parser.add(
        '--database-uri',
        metavar='URI',
        help=_(
            """Location of the database used for persistence. SQLite and PostgreSQL
            database are supported officially. To use a SQLite database you may
            define the location using a file path or a URI.
            e.g.: /srv/udb/file.db or sqlite:///srv/udb/file.db`.
            To use PostgreSQL server you must provide
            a URI similar to postgresql://user:pass@10.255.1.34/dbname and you
            must install required dependencies.
            By default, UDB uses a SQLite embedded database located at ./data.db"""
        ),
        default='sqlite:///data.db',
    )

    # Admin user
    parser.add_argument(
        '--admin-user',
        '--adminuser',
        metavar='USERNAME',
        help=_('administrator username. The administrator user get created on startup if the database is empty.'),
        default='admin',
    )

    parser.add_argument(
        '--admin-password',
        metavar='USERNAME',
        help=_(
            """administrator encrypted password as SSHA. Read online
            documentation to know more about how to encrypt your password
            into SSHA or use http://projects.marsching.org/weave4j/util/genpassword.php
            When defined, administrator password cannot be updated using the web interface.
            When undefined, default administrator password is `admin123` and
            it can be updated using the web interface."""
        ),
    )

    parser.add_argument(
        '--add-missing-user',
        '--addmissinguser',
        action='store_true',
        help=_('enable creation of users from LDAP when the credential are valid.'),
        default=False,
    )

    parser.add_argument(
        '--add-user-default-role',
        help=_(
            'default role used when creating users from LDAP. This parameter is only useful when `--add-missing-user` is enabled.'
        ),
        default='guest',
        choices=['admin', 'user', 'guest'],
    )

    # LDAP
    parser.add_argument(
        '--ldap-uri',
        help=_('URL to the LDAP server used to validate user credentials. e.g.: ldap://localhost:389'),
    )

    parser.add_argument(
        '--ldap-base-dn',
        '--ldapbasedn',
        metavar='DN',
        help=_('DN of the branch of the directory where all searches should start from. e.g.: dc=my,dc=domain'),
        default="",
    )

    parser.add_argument(
        '--ldap-scope',
        help=_('scope of the search. Can be either base, onelevel or subtree'),
        choices=['base', 'onelevel', 'subtree'],
        default="subtree",
    )

    parser.add_argument('--ldap-tls', '--ldaptls', action='store_true', help='enable TLS')

    parser.add_argument(
        '--ldap-username-attribute',
        metavar='ATTRIBUTE',
        help=_(
            "The attribute to search username. If no attributes are provided, the default is to use `uid`. It's a good idea to choose an attribute that will be unique across all entries in the subtree you will be using."
        ),
        default='uid',
    )

    parser.add_argument(
        '--ldap-user-filter',
        help=_(
            "search filter to limit LDAP lookup. If not provided, defaults to `(objectClass=*)`, which searches for all objects in the tree. For improved performance it's recommanded to narrow the search to your user object class. e.g.: `(objectClass=posixAccount)`"
        ),
        default='(objectClass=*)',
    )

    parser.add_argument(
        '--ldap-admin-group',
        metavar='CN',
        help=_("list of CN of the group(s) containing administrator. Not cn=groupname or the full DN."),
        action='append',
        default=[],
    )

    parser.add_argument(
        '--ldap-subnet-mgmt-group',
        metavar='CN',
        help=_("list of CN of the group(s) containing Subnet Managers. Not cn=groupname or the full DN."),
        action='append',
        default=[],
    )

    parser.add_argument(
        '--ldap-dnszone-mgmt-group',
        metavar='CN',
        help=_("list of CN of the group(s) containing DNS Zone Managers. Not cn=groupname or the full DN."),
        action='append',
        default=[],
    )

    parser.add_argument(
        '--ldap-user-group',
        metavar='CN',
        help=_("list of CN of the group(s) containing Users. Not cn=groupname or the full DN."),
        action='append',
        default=[],
    )

    parser.add_argument(
        '--ldap-guest-group',
        '--ldap-required-group',
        metavar='CN',
        help=_("list of CN of the group(s) containing Guests. Not cn=groupname or the full DN."),
        action='append',
        default=[],
    )

    parser.add_argument(
        '--ldap-group-filter',
        help=_(
            "search filter to limit LDAP lookup of groups. If not provided, defaults to `(objectClass=*)`, which searches for all objects in the tree. For improved performance it's recommanded to narrow the search to your group object class. e.g.: `(objectClass=posixGroup)`"
        ),
        default='(objectClass=*)',
    )

    parser.add_argument(
        '--ldap-group-attribute',
        metavar='ATTRIBUTE',
        help=_(
            "name of the attribute on the Group that hold the list of members. Default: `member`. Other common value is: `memberUid`"
        ),
        default='member',
    )

    parser.add_argument(
        '--ldap-group-attribute-is-dn',
        help=_("True If the group contains list of user defined with DN instead of username."),
        action='store_true',
    )

    parser.add_argument(
        '--ldap-bind-dn',
        metavar='DN',
        help=_(
            "optional DN used to bind to the server when searching for entries. If not provided, will use an anonymous bind."
        ),
        default="",
    )

    parser.add_argument(
        '--ldap-bind-password',
        metavar='PASSWORD',
        help=_(
            "password to use in conjunction with `--ldap-bind-dn`. Note that the bind password is probably sensitive data, and should be properly protected. You should only use the `--ldap-bind-dn` and `--ldap-bind-password` if you absolutely need them to search the directory."
        ),
        default="",
    )

    parser.add_argument(
        '--ldap-version',
        help=_("version of LDAP in use either 2 or 3. Default to 3."),
        default=3,
        type=int,
        choices=[2, 3],
    )

    parser.add_argument(
        '--ldap-network-timeout',
        metavar='SECONDS',
        help=_("timeout in seconds value used for LDAP connection"),
        default=100,
        type=int,
    )

    parser.add_argument(
        '--ldap-timeout',
        metavar='SECONDS',
        help=_("timeout in seconds value used for LDAP request"),
        default=300,
        type=int,
    )

    parser.add_argument(
        '--ldap-encoding',
        metavar='ENCODING',
        help=_("encoding used by your LDAP server."),
        default="utf-8",
    )

    parser.add_argument(
        '--ldap-fullname-attribute',
        help=_(
            "LDAP attribute for user display name. If `fullname` is blank, the fullname is taken from the `firstname` and `lastname`. Attributes 'cn', or 'displayName' commonly carry full names."
        ),
        default=[],
        action='append',
    )

    parser.add_argument(
        '--ldap-firstname-attribute',
        help=_(
            "LDAP attribute for user first name. Used when the attribute configured for name does not exist. e.g.: `givenName`"
        ),
        default=[],
        action='append',
    )

    parser.add_argument(
        '--ldap-lastname-attribute',
        help=_(
            "LDAP attribute for user last name. Used when the attribute configured for name does not exist. e.g.: `sn`"
        ),
        default=[],
        action='append',
    )

    parser.add_argument(
        '--ldap-email-attribute',
        help=_("LDAP attribute for user email. e.g.: mail, email, userPrincipalName"),
        default=[],
        action='append',
    )

    # Email
    parser.add_argument('--imap-server', metavar='SERVER', help=_('IMAP server used to reveive email.'))
    parser.add_argument(
        '--imap-username', metavar='USERNAME', help=_('Username used to authenticated with the IMAP server.')
    )
    parser.add_argument(
        '--imap-password', metavar='PASSWORD', help=_('Password used to authenticated with the IMAP server.')
    )
    parser.add_argument(
        '--imap-frequency', metavar='FREQUENCY', type=int, default=5, help=_('Delay between each IMAP request')
    )

    parser.add_argument('--smtp-server', metavar='SERVER', help=_('SMTP server used to send email.'))
    parser.add_argument(
        '--smtp-username', metavar='USERNAME', help=_('Username used to authenticated with the SMTP server.')
    )
    parser.add_argument(
        '--smtp-password', metavar='PASSWORD', help=_('Password used to authenticated with the SMTP server.')
    )
    parser.add_argument('--smtp-from', metavar='SERVER', help=_('Email address used to send email.'))
    parser.add_argument(
        '--smtp-encryption',
        default='none',
        choices=['none', 'ssl', 'starttls'],
        help=_('type of encryption to be used when establishing communication with SMTP server'),
    )

    parser.add_argument(
        '--notification-catch-all-email',
        metavar='EMAIL',
        help=_('When defined, all notification email will be sent to this email address.'),
        default=None,
    )

    parser.add_argument(
        '--favicon',
        dest='favicon',
        help='location of an icon to be used as a favicon displayed in web browser.',
    )

    parser.add_argument(
        '--header-logo',
        dest='header_logo',
        help='location of an image (preferably a .png) to be used as a replacement for the UDB header logo displayed in navigation bar.',
    )

    # Branding
    parser.add_argument(
        '--header-name',
        metavar='NAME',
        default='Universal Database',
        help=_('Name used in the title for this application.'),
    )
    parser.add_argument(
        '--footer-name',
        metavar='NAME',
        default='IKUS Soft UDB',
        help=_('Text displayed in the footer along "power by".'),
    )
    parser.add_argument(
        '--footer-url',
        metavar='URL',
        default="https://gitlab.com/ikus-soft/udb",
        help=_('URL used in the footer along "power by".'),
    )

    # Here we append a list of arguments for each locale.
    flags = ['--welcome-msg'] + ['--welcome-msg-' + i for i in ['ca', 'en', 'es', 'fr', 'ru']] + ['--welcomemsg']
    parser.add_argument(
        *flags,
        metavar='HTML',
        help=_('replace the welcome message displayed in the login page for default locale or for a specific locale'),
        action=LocaleAction
    )

    parser.add(
        '--password-score',
        type=lambda x: max(1, min(int(x), 4)),
        help=_(
            "Minimum zxcvbn's score for password. Value from 1 to 4. Default value 2. Read more about it here: https://github.com/dropbox/zxcvbn"
        ),
        default=2,
    )

    parser.add(
        '--umask',
        help=_(
            "Force a specific umask value. Usually expressed in octal format, for example, ``0022``. Default value is inherit from parent process."
        ),
        metavar='UMASK',
        type=_umask,
    )

    parser.add(
        '--user',
        help=_(
            "User under which the server will answer requests. In order to use this directive, the process must be run initially as root. If you start the server as a non-root user, it will fail to change to the lesser privileged user, and will instead continue to run as that original user."
        ),
        metavar='USER',
        type=_userid,
    )

    parser.add(
        '--group',
        help=_(
            "Group under which the server will answer requests. In order to use this directive, the process must be run initially as root."
        ),
        metavar='GROUP',
        type=_groupid,
    )

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
