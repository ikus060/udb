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

from udb.controller import url_for
from udb.controller.tests import WebCase
from udb.core.model import Rule

from .test_common_page import CommonTest


class RuleTest(WebCase, CommonTest):

    base_url = 'rule'

    obj_cls = Rule

    new_data = {
        'name': 'test',
        'model_name': 'subnet',
        'description': 'test',
        'statement': "SELECT id, 'subnet' as model_name, name as summary FROM subnet",
    }

    edit_data = {
        'name': 'new name',
        'statement': "SELECT id, 'subnet' as model_name, name as summary FROM subnet WHERE length(name)>10",
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
