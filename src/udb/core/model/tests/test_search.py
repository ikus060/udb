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

from sqlalchemy import func, or_

from udb.controller.tests import WebCase
from udb.core.model import DnsRecord, DnsZone, Ip, Message, Search, Subnet, Vrf


class SearchTest(WebCase):
    def test_search_without_term(self):
        # Given a database with records
        self.add_records()
        # When making a query without filter
        obj_list = Search.query.all()
        # Then all records are returned
        self.assertEqual(18, len(obj_list))

    def test_search_summary(self):
        # Given a database with records
        self.add_records()
        # When searching a term present in summary
        obj_list = Search.query.filter(func.udb_websearch(Search.search_string, 'DMZ')).order_by(Search.summary).all()
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
                    func.udb_websearch(Search.search_string, 'message'),
                    Search.messages.any(func.udb_websearch(Message.search_string, 'message')),
                )
            )
            .order_by(Search.summary)
            .all()
        )
        # Then records are returned.
        self.assertEqual(3, len(obj_list))
        self.assertEqual(['DMZ', 'bfh.ch', 'foo.bfh.ch = 147.87.250.3 (A)'], sorted([o.summary for o in obj_list]))

    def test_search_domain_name(self):
        # Given a DNS Record
        vrf = Vrf(name='default').add()
        subnet = Subnet(ranges=['192.168.1.0/24', '2001:db8:85a3::/64'], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        record = DnsRecord(name='lumos.example.com', type='A', value='192.168.1.14')
        record.add().commit()
        # When searching the first CN
        result = (
            Search.query.filter(
                func.udb_websearch(Search.search_string, 'lumos'),
            )
            .order_by(Search.summary)
            .all()
        )
        # Then search content should contains our DNS Record
        self.assertIn((record.id, 'dnsrecord'), [(r.model_id, r.model_name) for r in result])

    def test_search_subnet_ranges(self):
        # Given a subnet with ranges.
        vrf = Vrf(name='default').add()
        subnet = Subnet(ranges=['192.168.1.0/24', '2001:db8:85a3::/64'], vrf=vrf).add().commit()
        # When searching an ip address matching a ranges
        result = (
            Search.query.filter(
                func.udb_websearch(Search.search_string, '192.168.1'),
            )
            .order_by(Search.summary)
            .all()
        )
        # Then subnet is return.
        self.assertIn((subnet.id, 'subnet'), [(r.model_id, r.model_name) for r in result])

    def test_search_ipv4_address(self):
        # Given a DNS Record creating an ip address
        vrf = Vrf(name='default').add()
        subnet = Subnet(ranges=['192.168.1.0/24', '2001:db8:85a3::/64'], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        record = DnsRecord(name='lumos.example.com', type='A', value='192.168.1.14')
        record.add().commit()
        # When searching for partial IP Address 192.168
        result = (
            Search.query.filter(
                func.udb_websearch(Search.search_string, '192.168'),
            )
            .order_by(Search.summary)
            .all()
        )
        ip = Ip.query.filter(Ip.ip == record.generated_ip).one()
        # Then search content should contains our DNS Record
        self.assertIn((record.id, 'dnsrecord'), [(r.model_id, r.model_name) for r in result])
        # Then search content should also contain our IP
        self.assertIn((ip.id, 'ip'), [(r.model_id, r.model_name) for r in result])

    def test_search_ipv6_address(self):
        # Given a DNS Record creating an ip address
        vrf = Vrf(name='default').add()
        subnet = Subnet(ranges=['192.168.1.0/24', '	2a07:6b43::/32'], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        record = DnsRecord(name='lumos.example.com', type='AAAA', value='2a07:6b43:115:11::127')
        record.add().commit()
        # When searching for partial IP Address 2a07:6b43:115
        result = (
            Search.query.filter(
                func.udb_websearch(Search.search_string, '2a07:6b43:115'),
            )
            .order_by(Search.summary)
            .all()
        )
        ip = Ip.query.filter(Ip.ip == record.generated_ip).one()
        # Then search content should contains our DNS Record
        self.assertIn((record.id, 'dnsrecord'), [(r.model_id, r.model_name) for r in result])
        # Then search content should also contain our IP
        self.assertIn((ip.id, 'ip'), [(r.model_id, r.model_name) for r in result])
