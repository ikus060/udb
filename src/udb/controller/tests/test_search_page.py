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


from udb.controller.tests import WebCase
from udb.core.model import DhcpRecord, DnsRecord, DnsZone, Message, Subnet, User, Vrf


class TestSearchPage(WebCase):
    def add_records(self):
        self.user = User(username='test')
        self.vrf = Vrf(name='(default)')
        self.subnet = Subnet(
            ranges=['147.87.250.0/24'], name='DMZ', vrf=self.vrf, notes='public', owner=self.user
        ).add()
        self.subnet.add_message(Message(body='Message on subnet', author=self.user))
        Subnet(ranges=['147.87.0.0/16'], name='its-main-4', vrf=self.vrf, notes='main', owner=self.user).add()
        Subnet(
            ranges=['2002::1234:abcd:ffff:c0a8:101/64'], name='its-main-6', vrf=self.vrf, notes='main', owner=self.user
        ).add()
        Subnet(ranges=['147.87.208.0/24'], name='ARZ', vrf=self.vrf, notes='BE.net', owner=self.user).add()
        self.zone = DnsZone(name='bfh.ch', notes='DMZ Zone', subnets=[self.subnet], owner=self.user).add()
        self.zone.add_message(Message(body='Here is a message', author=self.user))
        self.zone.flush()
        DnsZone(name='bfh.science', notes='This is a note', owner=self.user).add()
        DnsZone(name='bfh.info', notes='This is a note', owner=self.user).add()
        DhcpRecord(ip='147.87.250.1', mac='00:ba:d5:a2:34:56', notes='webserver bla bla bla', owner=self.user).add()
        self.dnsrecord = DnsRecord(name='foo.bfh.ch', type='A', value='147.87.250.3', owner=self.user).add()
        self.dnsrecord.add_message(Message(body='This is a message', author=self.user))
        DnsRecord(name='bar.bfh.ch', type='A', value='147.87.250.1', owner=self.user).add()
        DnsRecord(name='bar.bfh.ch', type='CNAME', value='www.bar.bfh.ch', owner=self.user).add()
        DnsRecord(name='baz.bfh.ch', type='A', value='147.87.250.2', owner=self.user).add().commit()

    def test_search(self):
        # Given a database with records
        self.add_records()
        # When making a query to index page
        self.getPage('/search/')
        # Then an html page is returned
        self.assertStatus(200)
        self.assertInBody('Search')
        self.assertInBody('Sorry, that filter combination has no result.')

    def test_search_with_query(self):
        # Given a database with records
        self.add_records()
        # When making a query to the index page
        self.getPage('/search/query.json?q=public')
        # Then results are displayed
        self.assertStatus(200)
        self.assertInBody('DMZ')
