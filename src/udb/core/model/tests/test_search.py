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

from sqlalchemy import or_

from udb.controller.tests import WebCase
from udb.core.model import DhcpRecord, DnsRecord, DnsZone, Message, Search, Subnet, User, Vrf


class SearchTest(WebCase):
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
        DnsZone(name='bfh.science', notes='This is a note', owner=self.user).add()
        DnsZone(name='bfh.info', notes='This is a note', owner=self.user).add()
        DhcpRecord(ip='147.87.250.1', mac='00:ba:d5:a2:34:56', notes='webserver bla bla bla', owner=self.user).add()
        self.dnsrecord = DnsRecord(name='foo.bfh.ch', type='A', value='147.87.250.3', owner=self.user).add()
        self.dnsrecord.add_message(Message(body='This is a message', author=self.user))
        DnsRecord(name='bar.bfh.ch', type='A', value='147.87.250.1', owner=self.user).add()
        DnsRecord(name='bar.bfh.ch', type='CNAME', value='www.bar.bfh.ch', owner=self.user).add()
        DnsRecord(name='baz.bfh.ch', type='A', value='147.87.250.2', owner=self.user).add()

    def test_search_without_term(self):
        # Given a database with records
        self.add_records()
        # When making a query without filter
        obj_list = Search.query.all()
        # Then all records are returned
        self.assertEqual(13, len(obj_list))

    def test_search_summary(self):
        # Given a database with records
        self.add_records()
        # When searching a term present in summary
        obj_list = Search.query.filter(Search._search_vector.websearch('DMZ')).order_by(Search.summary).all()
        # Then records are returned.
        self.assertEqual(2, len(obj_list))
        self.assertEqual(['DMZ', 'bfh.ch'], sorted([obj.summary for obj in obj_list]))

    def test_search_messages(self):
        # Given a database with records
        self.add_records()
        # When searching a term present in summary
        obj_list = (
            Search.query.filter(
                or_(
                    Search._search_vector.websearch('message'),
                    Search.messages.any(Message._search_vector.websearch('message')),
                )
            )
            .order_by(Search.summary)
            .all()
        )
        # Then records are returned.
        self.assertEqual(3, len(obj_list))
        self.assertEqual(['DMZ', 'bfh.ch', 'foo.bfh.ch = 147.87.250.3(A)'], sorted([o.summary for o in obj_list]))
