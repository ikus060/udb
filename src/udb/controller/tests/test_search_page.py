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
from unittest.mock import ANY

from udb.controller import url_for
from udb.controller.tests import WebCase


class TestSearchPage(WebCase):
    def setUp(self):
        super().setUp()
        self.add_records()

    def test_search_empty(self):
        # Given a database with records
        # When making a query to search page
        self.getPage('/search/')
        # Then an html page is returned
        self.assertStatus(200)
        self.assertInBody('Sorry, that filter combination has no result.')

    def test_search_empty_json(self):
        # Given a database with records
        # When making a query to the search/data.json
        data = self.getJson('/search/data.json')
        # Then results is empty
        self.assertEqual(
            data,
            {'draw': None, 'recordsTotal': 0, 'recordsFiltered': 0, 'data': []},
        )

    def test_search_empty_selenium(self):
        # Given a database with records
        # When making a query to index page
        with self.selenium() as driver:
            driver.get(url_for('search'))
            driver.implicitly_wait(10)
            # Then the web page contains a table
            driver.find_element('css selector', 'table.table')
            # Then the web page is loaded without error.
            self.assertFalse(driver.get_log('browser'))
            # Then the table contains our result
            driver.find_element('xpath', "//*[contains(text(), 'Sorry, that filter combination has no result.')]")
            driver.find_element('xpath', "//*[contains(text(), 'No records available')]")

    def test_search(self):
        # Given a database with records
        # When making a query to the search page
        self.getPage('/search/?q=public')
        # Then Tabs get displayed
        self.assertInBody('All')
        self.assertInBody('Subnet')
        self.assertNotInBody('Vrf')
        self.assertNotInBody('Dns Zone')
        self.assertNotInBody('Dns Record')
        # Then the search page contains an ajax call
        self.assertStatus(200)
        self.assertInBody('/search/data.json?q=public')

    def test_search_json(self):
        # Given a database with records
        # When making a query to the index page
        data = self.getJson('/search/data.json?q=public')
        # Then results are displayed
        self.assertEqual(
            data,
            {
                'draw': None,
                'recordsTotal': 1,
                'recordsFiltered': 1,
                'data': [[1, 'enabled', 'DMZ', 'subnet', 'test', 'public', ANY, '/subnet/1/edit']],
            },
        )

    def test_search_selenium(self):
        # Given a database with records
        # When making a query to index page
        with self.selenium() as driver:
            driver.get(url_for('search', q='DMZ'))
            driver.implicitly_wait(10)
            # Then the web page contains a table
            driver.find_element('css selector', 'table.table')
            # Then the web page is loaded without error.
            self.assertFalse(driver.get_log('browser'))
            # Then the table contains a Subnet
            driver.find_element('xpath', "//*[contains(text(), 'DMZ')]")
            # Then the table contains a DNS Zone
            driver.find_element('xpath', "//*[contains(text(), 'bfh.ch')]")
            # Then tabs exists for subnet
            driver.find_element('xpath', "//button/*[contains(text(), 'All')]")
            dnszone_btn = driver.find_element('xpath', "//button/*[contains(text(), 'DNS Zone')]")
            driver.find_element('xpath', "//button/*[contains(text(), 'Subnet')]")
            # When user click on Tabs
            dnszone_btn.click()
            time.sleep(0.5)
            self.assertFalse(driver.get_log('browser'))
            # Then content is filtered and only DNS Zone is shown
            self.assertTrue(driver.find_element('xpath', "//*[contains(text(), 'bfh.ch')]").is_displayed())
            self.assertFalse(driver.find_element('xpath', "//*[contains(text(), 'DMZ')]").is_displayed())

    def test_typeahead_selenium(self):
        # Given a database with records
        with self.selenium() as driver:
            # When typing in search bar
            driver.implicitly_wait(10)
            driver.get(url_for('profile'))
            search_bar = driver.find_element('css selector', 'input.js-typeahead')
            search_bar.click()
            search_bar.send_keys('DMZ')
            # Then the web page is loaded without error.
            self.assertFalse(driver.get_log('browser'))
            # Then typeahead displays suggestions
            driver.find_element('xpath', "//*[contains(text(), 'DMZ')]")
