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

from udb.controller import url_for
from udb.controller.tests import WebCase
from udb.core.model import Rule

from .test_common_page import CommonTest


class RulePageTest(WebCase, CommonTest):

    base_url = 'rule'

    obj_cls = Rule

    new_data = {
        'name': 'test',
        'model_name': 'subnet',
        'description': 'test',
        'statement': "SELECT id, name FROM subnet",
    }

    edit_data = {
        'name': 'new name',
        'statement': "SELECT id, name FROM subnet WHERE length(name)>10",
    }

    def setUp(self):
        super().setUp()
        # Delete existing rule
        Rule.query.delete()
        Rule.session.commit()

    def test_linter_json(self):
        # Given a database with records
        self.add_records()
        # When querying the database for linter
        data = self.getJson(url_for('rule', 'linter.json'))
        # Then data is returned
        self.assertIsNotNone(data)


class BuiltinRuleTest(WebCase):
    def test_edit_builtin_fail(self):
        # Given a builtin rule
        rule = Rule.query.filter(Rule.builtin.is_(True)).first()
        # When trying to change the builtin state
        self.getPage(url_for('rule', rule.id, 'edit'), method='POST', body={'builtin': 0})
        self.assertStatus(303)
        # Then nothing happen
        rule.expire()
        self.assertTrue(rule.builtin)

    @parameterized.expand(
        [
            (Rule.SEVERITY_ENFORCED, 'UPPERCASE', True),
            (Rule.SEVERITY_ENFORCED, 'lowercase', False),
            (Rule.SEVERITY_SOFT, 'UPPERCASE', False),
            (Rule.SEVERITY_SOFT, 'lowercase', False),
        ]
    )
    def test_soft_vs_enforced_rule_edit(self, severity, vrf_name, expect_failure):
        # Given a enforced rule on VRF name
        Rule(
            name='test_vrf',
            model_name='vrf',
            statement="SELECT id, name from vrf where name != lower(name)",
            description='VRF Name must be in lower case',
            severity=severity,
        ).add().commit()
        # When trying to create a VRF that infring the rule
        self.getPage(url_for('vrf', 'new'), method='POST', body={'name': vrf_name})
        # Then an error message is displayed to the user
        if expect_failure:
            self.assertStatus(200)
            self.assertInBody('VRF Name must be in lower case')
        else:
            self.assertStatus(303)
