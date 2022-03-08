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

import unittest

from udb.config import parse_args


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
