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
    def setUp(self):
        super().setUp()
        self.add_records()

    @parameterized.expand(
        [
            # Invalid SQL
            ('INVALID STATEMENT', True),
            # All column
            ('SELECT * from subnet', True),
            # Only 1 column
            ('SELECT id from subnet', True),
            # Wrong column name column name
            ("SELECT id, notes from subnet", True),
            # Wrong table
            ("SELECT id, name from vrf", True),
            # Valid 2 columns
            ("SELECT id, name from subnet", False),
        ]
    )
    def test_with_valid_vs_invalid_statement(self, statement, expect_failure):
        # Given an SQL statement
        # When trying to create the rule
        rule = Rule(name='test', description='test', statement=statement, model_name='subnet')
        # Then an error is raised
        if expect_failure:
            with self.assertRaises(ValueError) as context:
                rule.add().commit()
            self.assertEqual('statement', context.exception.args[0])
        else:
            rule.add().commit()
