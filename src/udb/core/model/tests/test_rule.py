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


from parameterized import parameterized

from udb.controller.tests import WebCase
from udb.core.model import Rule


class RuleTest(WebCase):
    @parameterized.expand(
        [
            ('INVALID STATEMENT'),
            ('SELECT * from subnet'),
            ('SELECT id from subnet'),
        ]
    )
    def test_with_invalid_statement(self, statement):
        # Given an invalid statement
        # When trying to create the rule
        # Then an error is raised
        with self.assertRaises(ValueError):
            Rule(name='test', description='test', statement=statement)
