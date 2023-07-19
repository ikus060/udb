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

from selenium.common.exceptions import NoSuchElementException

from udb.controller import url_for
from udb.controller.tests import WebCase
from udb.core.model import DnsRecord, DnsZone, Subnet, SubnetRange, Vrf


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
            driver.implicitly_wait(3)
            # Then the web page contains a table
            driver.find_element('css selector', 'table.table')
            # Then the web page is loaded without error.
            self.assertFalse(driver.get_log('browser'))
            # Then the table contains a Subnet
            driver.find_element('xpath', "//*[contains(text(), 'public')]")
            # Then the table contains a DNS Zone
            driver.find_element('xpath', "//*[contains(text(), 'DMZ Zone')]")
            # Then tabs exists for subnet
            driver.find_element('xpath', "//button/*[contains(text(), 'All')]")
            dnszone_btn = driver.find_element('xpath', "//button/*[contains(text(), 'DNS Zone')]")
            driver.find_element('xpath', "//button/*[contains(text(), 'Subnet')]")
            # When user click on Tabs
            dnszone_btn.click()
            time.sleep(0.5)
            self.assertFalse(driver.get_log('browser'))
            # Then content is filtered and only DNS Zone is shown
            self.assertTrue(driver.find_element('xpath', "//*[contains(text(), 'DMZ Zone')]").is_displayed())
            with self.assertRaises(NoSuchElementException):
                driver.find_element('xpath', "//*[contains(text(), 'public')]")

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

    def test_search_with_active_model_name_selenium(self):
        # Given a database with records
        # When making a query to the search page with default model_name selected
        with self.selenium() as driver:
            driver.implicitly_wait(10)
            driver.get(url_for('search', q='147', subnet='1'))
            # Then Subnet Tabs is selected
            active_btn = driver.find_element('css selector', 'button.nav-link.active')
            self.assertEqual("Subnet 3", active_btn.text)
            # Then Matching DNS Record are not shown
            driver.implicitly_wait(1)
            with self.assertRaises(NoSuchElementException):
                driver.find_element('xpath', "//*[contains(text(), 'bar.bfh.ch')]")

    def test_data_json_without_term(self):
        # When making a query without filter
        data = self.getJson(url_for("search", "data.json", q=""))
        # Then nothing is returned
        self.assertEqual(data, {'draw': None, 'recordsTotal': 0, 'recordsFiltered': 0, 'data': []})

    def test_data_json_summary(self):
        # Given a database with records
        # When searching a term present in summary
        data = self.getJson(url_for("search", "data.json", q="DMZ"))
        # Then records are returned.
        self.assertEqual(
            data,
            {
                'draw': None,
                'recordsTotal': 2,
                'recordsFiltered': 2,
                'data': [
                    [
                        1,
                        'enabled',
                        'bfh.ch',
                        'dnszone',
                        'test',
                        'DMZ Zone',
                        ANY,
                        '/dnszone/1/edit',
                    ],
                    [
                        1,
                        'enabled',
                        'DMZ',
                        'subnet',
                        'test',
                        'public',
                        ANY,
                        '/subnet/1/edit',
                    ],
                ],
            },
        )

    def test_data_json_search_with_model_name(self):
        # Given a database with records
        # When searching for a specific model_name
        data = self.getJson(url_for("search", "data.json", **{"q": "DMZ", "columns[3][search][value]": "dnszone"}))
        # Then results only contains our model name
        self.assertEqual(
            data,
            {
                'draw': None,
                'recordsTotal': 1,
                'recordsFiltered': 1,
                'data': [[1, 'enabled', 'bfh.ch', 'dnszone', 'test', 'DMZ Zone', ANY, '/dnszone/1/edit']],
            },
        )
        # When searching for a specific model_name
        data = self.getJson(url_for("search", "data.json", **{"q": "DMZ", "columns[3][search][value]": "subnet"}))
        # Then results only contains our model name
        self.assertEqual(
            data,
            {
                'draw': None,
                'recordsTotal': 1,
                'recordsFiltered': 1,
                'data': [[1, 'enabled', 'DMZ', 'subnet', 'test', 'public', ANY, '/subnet/1/edit']],
            },
        )

    def test_data_json_search_domain_name(self):
        # Given a DNS Record
        vrf = Vrf(name='default').add()
        subnet = Subnet(subnet_ranges=[SubnetRange('192.168.1.0/24'), SubnetRange('2001:db8:85a3::/64')], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        record = DnsRecord(name='lumos.example.com', type='A', value='192.168.1.14')
        record.add().commit()
        # When searching the first CN
        data = self.getJson(url_for("search", "data.json", q="lumos"))
        # Then search content should contains our DNS Record
        self.assertEqual(
            data,
            {
                'draw': None,
                'recordsTotal': 1,
                'recordsFiltered': 1,
                'data': [
                    [
                        5,
                        'enabled',
                        'lumos.example.com = 192.168.1.14 (A)',
                        'dnsrecord',
                        None,
                        '',
                        ANY,
                        '/dnsrecord/5/edit',
                    ]
                ],
            },
        )

    def test_data_json_search_subnet_ranges(self):
        # Given a subnet with ranges.
        vrf = Vrf(name='default').add()
        Subnet(subnet_ranges=[SubnetRange('192.168.1.0/24'), SubnetRange('2001:db8:85a3::/64')], vrf=vrf).add().commit()
        # When searching an ip address matching a ranges
        data = self.getJson(url_for("search", "data.json", q="192.168.1"))
        # Then subnet is return.
        self.assertEqual(
            data,
            {
                'draw': None,
                'recordsTotal': 1,
                'recordsFiltered': 1,
                'data': [
                    [
                        5,
                        'enabled',
                        '',
                        'subnet',
                        None,
                        '',
                        ANY,
                        '/subnet/5/edit',
                    ]
                ],
            },
        )

    def test_data_json_search_ipv4_address(self):
        # Given a DNS Record creating an ip address
        vrf = Vrf(name='default').add()
        subnet = Subnet(subnet_ranges=[SubnetRange('192.168.1.0/24'), SubnetRange('2001:db8:85a3::/64')], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        record = DnsRecord(name='lumos.example.com', type='A', value='192.168.1.14')
        record.add().commit()
        # When searching for partial IP Address 192.168
        data = self.getJson(url_for("search", "data.json", q="192.168"))
        # Then search content should contains our DNS Record
        # Then search content should also contain our IP
        self.assertEqual(
            data,
            {
                'draw': None,
                'recordsTotal': 3,
                'recordsFiltered': 3,
                'data': [
                    [
                        5,
                        'enabled',
                        'lumos.example.com = 192.168.1.14 (A)',
                        'dnsrecord',
                        None,
                        '',
                        ANY,
                        '/dnsrecord/5/edit',
                    ],
                    [
                        4,
                        'enabled',
                        '192.168.1.14',
                        'ip',
                        None,
                        '',
                        ANY,
                        '/ip/4/edit',
                    ],
                    [
                        5,
                        'enabled',
                        '',
                        'subnet',
                        None,
                        '',
                        ANY,
                        '/subnet/5/edit',
                    ],
                ],
            },
        )

    def test_data_json_search_ipv6_address(self):
        # Given a DNS Record creating an ip address
        vrf = Vrf(name='default').add()
        subnet = Subnet(subnet_ranges=[SubnetRange('192.168.1.0/24'), SubnetRange('	2a07:6b43::/32')], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        record = DnsRecord(name='lumos.example.com', type='AAAA', value='2a07:6b43:115:11::127')
        record.add().commit()
        # When searching for partial IP Address 2a07:6b43:115
        data = self.getJson(url_for("search", "data.json", q="2a07:6b43:115"))
        # Then search content should contains our DNS Record
        # Then search content should also contain our IP
        self.assertEqual(
            data,
            {
                'draw': None,
                'recordsTotal': 2,
                'recordsFiltered': 2,
                'data': [
                    [
                        5,
                        'enabled',
                        'lumos.example.com = 2a07:6b43:115:11::127 (AAAA)',
                        'dnsrecord',
                        None,
                        '',
                        ANY,
                        '/dnsrecord/5/edit',
                    ],
                    [
                        4,
                        'enabled',
                        '2a07:6b43:115:11::127',
                        'ip',
                        None,
                        '',
                        ANY,
                        '/ip/4/edit',
                    ],
                ],
            },
        )

    def test_typeahead_json(self):
        # Given a database with records
        # When using typeahead
        data = self.getJson(url_for("search", "typeahead.json", q="DMZ"))
        # Then is contains results
        self.assertEqual(
            data,
            {
                'status': 200,
                'data': [
                    {'model_id': 1, 'model_name': 'subnet', 'summary': 'DMZ', 'url': '/subnet/1/edit'},
                    {'model_id': 1, 'model_name': 'dnszone', 'summary': 'bfh.ch', 'url': '/dnszone/1/edit'},
                ],
            },
        )
