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
from udb.core.model import DnsZone, Message, Search


class TestApp(WebCase):
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
        msg = Message.query.first()
        # Then URL is create with object name and object id
        self.assertEqual(url_for(msg), 'http://%s:%s/dnszone/%s' % (self.HOST, self.PORT, obj.id))

    def test_url_for_with_search(self):
        # Given a database with a record
        obj = DnsZone(name='bfh.ch').add()
        obj.commit()
        # When creating URL using the search object
        msg = Search.query.first()
        # Then URL is create with object name and object id
        self.assertEqual(url_for(msg), 'http://%s:%s/dnszone/%s' % (self.HOST, self.PORT, obj.id))

    def test_with_proxy(self):
        self.getPage('/dashboard/', headers=[('Host', 'www.example.test')])
        self.assertInBody('http://www.example.test/static/main.css')
        self.assertInBody('http://www.example.test/static/main.js')
        self.assertInBody('http://www.example.test/static/favicon.svg')

    def test_with_https_proxy(self):
        self.getPage('/dashboard/', headers=[('Host', 'www.example.test'), ('X-Forwarded-Proto', 'https')])
        self.assertInBody('https://www.example.test/static/main.css')
        self.assertInBody('https://www.example.test/static/main.js')
        self.assertInBody('https://www.example.test/static/favicon.svg')

    def test_with_forwarded_host_ignored(self):
        self.getPage('/dashboard/', headers=[('X-Forwarded-Host', 'https://www.example.test')])
        self.assertNotInBody('https://www.example.test/')
