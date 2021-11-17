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

import sys

import configargparse

# Get package version
try:
    import pkg_resources
    __version__ = pkg_resources.get_distribution("cmdb").version
except Exception:
    __version__ = 'DEV'


def parse_args(args=None, config_file_contents=None):
    """
    Load application configuration using program's arguments or environment variables.
    """
    args = sys.argv[1:] if args is None else args

    parser = configargparse.ArgumentParser(
        description='A web interface to manage IT network CMDB',
        add_env_var_help=True,
        auto_env_var_prefix='CMDB_',)
    parser.add_argument(
        '-d', '--debug',
        action='store_true',
        help='enable debug mode - change the log level to DEBUG, print exception stack trace to the web interface')
    parser.add_argument(
        '-f', '--config', is_config_file=True, help='configuration file path')
    parser.add_argument(
        '-v', '--version', action='version', version='cmdb ' + __version__)
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

    # Branding
    parser.add_argument(
        '--header-name', metavar='NAME', default='cmdb',
        help='Name used in the title for this application.')
    parser.add_argument(
        '--footer-name', metavar='NAME', default='cmdb',
        help='Text displayed in the footer along "power by".')
    parser.add_argument(
        '--footer-url', metavar='URL', default="https://gitlab.com/ikus-soft/cmdb",
        help='URL used in the footer along "power by".')

    return parser.parse_args(args, config_file_contents=config_file_contents)
