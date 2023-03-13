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

import time
from base64 import b64encode
from unittest.mock import ANY

from parameterized import parameterized

from udb.controller import url_for
from udb.controller.tests import WebCase


class AuditPageTest(WebCase):

    base_url = 'audit'

    new_data = {}

    authorization = [('Authorization', 'Basic %s' % b64encode(b'admin:admin').decode('ascii'))]

    def setUp(self):
        super().setUp()
        self.add_records()

    def test_get_list(self):
        # Given a database with changes
        # When making a query to audit log
        self.getPage(url_for(self.base_url, ''))
        # Then an html page is returned with a table
        self.assertStatus(200)
        self.assertInBody('<table')

    def test_get_list_page_selenium(self):
        # Given a database with changes
        with self.selenium() as driver:
            # When making a query to audit log
            driver.get(url_for(self.base_url, ''))
            driver.implicitly_wait(10)
            # Then the web page contains a table
            driver.find_element('css selector', 'table.table')
            time.sleep(1)
            # Then the web page is loaded without error.
            self.assertFalse(driver.get_log('browser'))
            # Then the table contains at least a changes in Environment
            driver.find_element('xpath', "//*[contains(text(), 'echo FOO')]")

    def test_data_json(self):
        # Given a query to data_json
        data = self.getJson(url_for(self.base_url, 'data.json'))
        # Then a response is return with latest changes
        self.assertEqual(data, {'draw': None, 'recordsTotal': 18, 'recordsFiltered': 18, 'data': ANY})
        self.assertEqual(10, len(data['data']))

    def test_data_json_with_length(self):
        # Given a query to data_json
        data = self.getJson(url_for(self.base_url, 'data.json', length=5))
        # Then a response is return with latest changes
        self.assertEqual(data, {'draw': None, 'recordsTotal': 18, 'recordsFiltered': 18, 'data': ANY})
        self.assertEqual(5, len(data['data']))

    def test_data_json_with_start(self):
        # Given a query to data_json
        data = self.getJson(url_for(self.base_url, 'data.json', start=5, length=5))
        # Then a response is return with latest changes
        self.assertEqual(data, {'draw': None, 'recordsTotal': 18, 'recordsFiltered': 18, 'data': ANY})
        self.assertEqual(5, len(data['data']))

    def test_data_json_with_search(self):
        # Given a query to data_json
        data = self.getJson(url_for(self.base_url, 'data.json', **{'search[value]': 'test'}))
        # Then a response is return with latest changes
        self.assertEqual(data, {'draw': None, 'recordsTotal': 18, 'recordsFiltered': 1, 'data': ANY})
        self.assertEqual(1, len(data['data']))

    @parameterized.expand(['0', '1', '2', '3', '4', '5', '6'])
    def test_data_json_with_order(self, col_idx):
        # Given a query to data_json
        self.getJson(url_for(self.base_url, 'data.json', **{'order[0][column]': col_idx}))
        self.getJson(url_for(self.base_url, 'data.json', **{'order[0][column]': col_idx, 'order[0][dir]': 'asc'}))
        self.getJson(url_for(self.base_url, 'data.json', **{'order[0][column]': col_idx, 'order[0][dir]': 'desc'}))
