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

from udb.controller import _find_constraint, url_for
from udb.controller.tests import WebCase
from udb.core.model import DnsZone


class TestController(WebCase):
    def test_url_for_with_relative(self):
        self.assertEqual(
            url_for(DnsZone, relative=True),
            '%s:%s/dnszone/' % (self.HOST, self.PORT),
        )
        self.assertEqual(
            url_for(DnsZone, 'new', relative='server'),
            '/dnszone/new',
        )

    def test_url_for_with_model(self):
        self.assertEqual(url_for(DnsZone), 'http://%s:%s/dnszone/' % (self.HOST, self.PORT))
        self.assertEqual(url_for(DnsZone, 'new'), 'http://%s:%s/dnszone/new' % (self.HOST, self.PORT))

    def test_url_for_with_object(self):
        # Given a database with a record
        obj = DnsZone(name='bfh.ch').add()
        obj.commit()
        # When creating URL for that object
        # Then URL is create with object name and object id
        self.assertEqual(url_for(obj), 'http://%s:%s/dnszone/%s' % (self.HOST, self.PORT, obj.id))

    def test_url_for_with_message(self):
        # Given a database with a record
        obj = DnsZone(name='bfh.ch').add()
        obj.commit()
        # When creating URL using the message
        msg = obj.messages[-1]
        # Then URL is create with object name and object id
        self.assertEqual(url_for(msg), 'http://%s:%s/dnszone/%s' % (self.HOST, self.PORT, obj.id))

    def test_with_proxy(self):
        self.getPage('/dashboard/', headers=[('Host', 'www.example.test')])
        self.assertInBody('http://www.example.test/static/main.css')
        self.assertInBody('http://www.example.test/static/main.js')
        self.assertInBody('http://www.example.test/static/favicon')

    def test_with_https_proxy(self):
        self.getPage('/dashboard/', headers=[('Host', 'www.example.test'), ('X-Forwarded-Proto', 'https')])
        self.assertInBody('https://www.example.test/static/main.css')
        self.assertInBody('https://www.example.test/static/main.js')
        self.assertInBody('https://www.example.test/static/favicon')

    def test_with_forwarded_host_ignored(self):
        self.getPage('/dashboard/', headers=[('X-Forwarded-Host', 'https://www.example.test')])
        self.assertNotInBody('https://www.example.test/')

    @parameterized.expand(
        [
            # Postgresql: Foreign constraint
            (
                "dnsrecord_dnszone_subnet_fk",
                'update or delete on table "dnszone_subnet" violates foreign key constraint "dnsrecord_dnszone_subnet_fk" on table "dnsrecord"',
            ),
            # Postgresql: UNIQUE constraint
            (
                "user_username_unique_ix",
                'duplicate key value violates unique constraint "user_username_unique_ix"',
            ),
            # Postgresql: CHECK constraint
            (
                "dnsrecord_types_ck",
                'violates check constraint "dnsrecord_types_ck"',
            ),
            # SQLite: UNIQUE constraint
            (
                "user_username_unique_ix",
                "UNIQUE constraint failed: index 'user_username_unique_ix'",
            ),
            # SQLite: UNIQUE constrain
            ("dhcprecord_mac_unique_ix", "UNIQUE constraint failed: dhcprecord.mac"),
            # SQLite: CHECK constraint
            ("dnsrecord_types_ck", "SQLite: CHECK constraint failed: dnsrecord_types_ck"),
        ]
    )
    def test_find_constraint(self, expected_rule, error_msg):
        # Given an error message
        # When searching for corresponding constraint
        constraint = _find_constraint(error_msg)
        # Then constraint is found or not
        if expected_rule:
            self.assertIsNotNone(constraint, 'expecting constaint to be found')
            self.assertEqual(expected_rule, constraint.name)
        else:
            self.assertIsNone(constraint, 'not existing a constraint to be found')
