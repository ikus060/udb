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

import grp
import os
import unittest

from udb.config import parse_args

try:
    _login = os.getlogin()
except Exception:
    _login = None


class TestConfig(unittest.TestCase):
    def test_parse_args(self):
        # Given a valid list of arguemnts
        args = [
            '--server-host',
            '1.2.3.4',
            '--server-port',
            '5000',
            '--log-file',
            '/path/to/log',
            '--log-access-file',
            '/path/to/log2',
        ]
        # When parsing the arguments list
        cfg = parse_args(args)
        # Then configuration matches the arguments value
        self.assertEqual(cfg.server_host, '1.2.3.4')
        self.assertEqual(cfg.server_port, 5000)
        self.assertEqual(cfg.log_file, '/path/to/log')
        self.assertEqual(cfg.log_access_file, '/path/to/log2')

    def test_parse_ldap_fullname_attribute(self):
        # Given a valid list of arguemnts
        args = ['--ldap-fullname-attribute', 'sn']
        # When parsing the arguments list
        cfg = parse_args(args)
        # Then configuration matches the arguments value
        self.assertEqual(cfg.ldap_fullname_attribute, ['sn'])

    def test_uid_gid_umask(self):
        # Given username, group define using id.
        args = [
            '--server-host',
            '1.2.3.4',
            '--server-port',
            '5000',
            '--user',
            '123',
            '--group',
            '123',
            '--umask',
            '0002',
        ]
        # When parsing the arguments list
        cfg = parse_args(args)
        # Then configuration return integer value.
        self.assertEqual(cfg.user, 123)
        self.assertEqual(cfg.group, 123)
        self.assertEqual(cfg.umask, 0o0002)

    @unittest.skipIf(_login is None, reason="real username required to run to this test")
    def test_user_group_umask(self):
        # Given username, group define using name.
        args = [
            '--server-host',
            '1.2.3.4',
            '--server-port',
            '5000',
            '--user',
            _login,
            '--group',
            grp.getgrgid(os.getgid()).gr_name,
        ]
        # When parsing the arguments list
        cfg = parse_args(args)
        # Then username and group are resolved as uid, gid
        self.assertEqual(cfg.user, os.getuid())
        self.assertEqual(cfg.group, os.getgid())

    def test_ldap_group(self):
        # Given a ldap-admin-group define in arguments
        args = [
            '--server-host',
            '1.2.3.4',
            '--server-port',
            '5000',
            '--ldap-admin-group',
            'udb-admin',
            '--ldap-admin-group',
            'udb-devops',
        ]
        # When parsing the arguments list
        cfg = parse_args(args)
        # Then ldap-admin-group is an array
        self.assertEqual(cfg.ldap_admin_group, ['udb-admin', 'udb-devops'])
        # Then other group are defined as empty array
        self.assertEqual(cfg.ldap_subnet_mgmt_group, [])
        self.assertEqual(cfg.ldap_dnszone_mgmt_group, [])
        self.assertEqual(cfg.ldap_user_group, [])
        self.assertEqual(cfg.ldap_guest_group, [])
