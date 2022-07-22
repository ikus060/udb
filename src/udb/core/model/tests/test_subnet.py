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

from unittest import mock

from sqlalchemy.exc import IntegrityError

from udb.controller.tests import WebCase
from udb.core.model import DnsZone, Subnet, Vrf


class SubnetTest(WebCase):
    def test_json(self):
        # Given a DnsZone
        vrf = Vrf(name='default')
        obj = Subnet(name='test', ip_cidr='192.168.1.0/24', vrf=vrf).add()
        # When serializing the object to json
        data = obj.to_json()
        # Then a json representation is return
        self.assertEqual(
            data,
            {
                'depth': 0,
                'created_at': mock.ANY,
                'id': 1,
                'ip_cidr': '192.168.1.0/24',
                'modified_at': mock.ANY,
                'name': 'test',
                'notes': '',
                'owner_id': None,
                'status': 'enabled',
                'vrf_id': vrf.id,
                'l3vni': None,
                'l2vni': None,
                'vlan': None,
            },
        )

    def test_add_ipv4(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with IPV4
        Subnet(ip_cidr='192.168.1.0/24').add()
        # Then a new record is created
        subnet = Subnet.query.first()
        self.assertEqual('192.168.1.0/24', subnet.ip_cidr)

    def test_add_ipv6(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with IPV6
        Subnet(ip_cidr='2002::1234:abcd:ffff:c0a8:101/64').add()
        # Then a new record is created
        subnet = Subnet.query.first()
        self.assertEqual('2002:0:0:1234::/64', subnet.ip_cidr)

    def test_invalid_ipv4(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with an invalid IP
        with self.assertRaises(ValueError) as cm:
            Subnet(ip_cidr='a.168.1.0/24').add()
        self.assertEqual(cm.exception.args, ('ip_cidr', mock.ANY))
        # Then a record is not created
        self.assertEqual(0, Subnet.query.count())

    def test_missing_ipv4(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet without an IP
        with self.assertRaises(IntegrityError):
            Subnet(name='foo').add()
        self.session.rollback()
        # Then a record is not created
        self.assertEqual(0, Subnet.query.count())

    def test_add_with_vrf(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with a VRF
        vrf = Vrf(name='test').add()
        Subnet(ip_cidr='192.168.1.0/24', vrf=vrf).add()
        # Then a new record is created
        self.assertEqual(1, Subnet.query.count())

    def test_add_with_name(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with a name
        Subnet(ip_cidr='192.168.1.0/24', name='foo').add()
        # Then a new record is created
        self.assertEqual(1, Subnet.query.count())

    def test_duplicate_ip_cidr(self):
        # Given a database with an existing record
        Subnet(ip_cidr='192.168.1.0/24', name='foo', vrf=None).add()
        self.assertEqual(1, Subnet.query.count())
        # When trying to add a Subnet with an existing ip_CIDR
        # Then an exception is raised
        with self.assertRaises(IntegrityError):
            Subnet(ip_cidr='192.168.1.0/24', name='bar', vrf=None).add()

    def test_duplicate_ip_cidr_with_vrf(self):
        # Given a database with an existing record
        vrf = Vrf(name='default')
        Subnet(ip_cidr='192.168.1.0/24', name='foo', vrf=vrf).add()
        self.assertEqual(1, Subnet.query.count())
        # When trying to add a Subnet with an existing IP CIDR in a different VRF
        subnet = Subnet(ip_cidr='192.168.1.0/24', name='bar', vrf=None).add()
        # Then subnet is created without error
        self.assertIsNotNone(subnet)
        # When trying to add a Subnet with an existing IP CIDR in same VRF
        # Then an exception is raised
        with self.assertRaises(IntegrityError):
            Subnet(ip_cidr='192.168.1.0/24', name='bar', vrf=vrf).add()

    def test_add_dnszonesubnet(self):
        # Given a database with an existing record
        subnet = Subnet(ip_cidr='192.168.1.0/24', name='foo').add()
        self.session.commit()
        # When trying to add an allowed subnet to the dns zone
        zone = DnsZone(name='bfh.ch').add()
        subnet.dnszones.append(zone)
        zone.add()
        # Then a subnet is added
        subnet = Subnet.query.first()
        zone = DnsZone.query.first()
        self.assertEqual(1, len(subnet.dnszones))
        self.assertEqual('bfh.ch', subnet.dnszones[0].name)
        self.assertEqual(1, len(subnet.dnszones[0].subnets))
        self.assertEqual(subnet, subnet.dnszones[0].subnets[0])
        # Then an audit message is created for both objects
        self.assertEqual(2, len(subnet.messages))
        self.assertEqual(subnet.messages[-1].changes, {'dnszones': [[], ['bfh.ch']]})
        self.assertEqual(2, len(zone.messages))
        self.assertEqual(zone.messages[-1].changes, {'subnets': [[], ['192.168.1.0/24 (foo)']]})

    def test_subnets(self):
        # Given a database with an existing record
        subnet1 = Subnet(ip_cidr='192.168.1.0/24', name='foo').add()
        subnet2 = Subnet(ip_cidr='192.168.1.128/30', name='bar').add()
        subnet3 = Subnet(ip_cidr='10.255.0.0/16', name='tor').add()
        subnet4 = Subnet(ip_cidr='192.0.2.23', name='fin').add()
        subnet5 = Subnet(ip_cidr='2a07:6b40::/32', name='infra').add()
        subnet6 = Subnet(ip_cidr='2a07:6b40:0::/48', name='infra-any-cast').add()
        subnet7 = Subnet(ip_cidr='2a07:6b40:0:0::/64', name='infra-any-cast').add()
        subnet8 = Subnet(ip_cidr='2a07:6b40:1::/48', name='all-anycast-infra-test').add()
        # When querying list of subnets
        # Then the list contains our subnet
        self.assertEqual([subnet2], subnet1.related_subnets)
        self.assertEqual([], subnet2.related_subnets)
        self.assertEqual([], subnet3.related_subnets)
        self.assertEqual([], subnet4.related_subnets)
        self.assertEqual([subnet6, subnet7, subnet8], subnet5.related_subnets)
        self.assertEqual([subnet7], subnet6.related_subnets)
        self.assertEqual([], subnet7.related_subnets)
        self.assertEqual([], subnet8.related_subnets)

    def test_supernets(self):
        # Given a database with an existing record
        subnet1 = Subnet(ip_cidr='192.168.1.0/24', name='foo').add()
        subnet2 = Subnet(ip_cidr='192.168.1.128/30', name='bar').add()
        subnet3 = Subnet(ip_cidr='10.255.0.0/16', name='tor').add()
        subnet4 = Subnet(ip_cidr='192.0.2.23', name='fin').add()
        subnet5 = Subnet(ip_cidr='2a07:6b40::/32', name='infra').add()
        subnet6 = Subnet(ip_cidr='2a07:6b40:0::/48', name='infra-any-cast').add()
        subnet7 = Subnet(ip_cidr='2a07:6b40:0:0::/64', name='infra-any-cast').add()
        subnet8 = Subnet(ip_cidr='2a07:6b40:1::/48', name='all-anycast-infra-test').add()
        # When querying list of subnets
        # Then the list contains our subnet
        self.assertEqual([], subnet1.related_supernets)
        self.assertEqual([subnet1], subnet2.related_supernets)
        self.assertEqual([], subnet3.related_supernets)
        self.assertEqual([], subnet4.related_supernets)
        self.assertEqual([], subnet5.related_supernets)
        self.assertEqual([subnet5], subnet6.related_supernets)
        self.assertEqual([subnet5, subnet6], subnet7.related_supernets)
        self.assertEqual([subnet5], subnet8.related_supernets)

    def test_depth(self):
        # Given a database with an existing record
        subnet1 = Subnet(ip_cidr='192.168.1.0/24', name='foo').add()
        subnet2 = Subnet(ip_cidr='192.168.1.128/30', name='bar').add()
        self.assertEqual(1, len(subnet1.messages))
        self.assertEqual(1, len(subnet2.messages))
        # When querying depth
        subnets = Subnet.query_with_depth()
        # Then the depth matches the subnet indentation
        self.assertEqual(0, subnets[0].depth)
        self.assertEqual(1, subnets[1].depth)
        # Then existing object are also updated
        self.assertEqual(0, subnet1.depth)
        self.assertEqual(1, subnet2.depth)
        # Then not messages get created for depth changes
        self.assertEqual(1, len(subnet1.messages))
        self.assertEqual(1, len(subnet2.messages))

    def test_depth_select(self):
        # Given a database with an existing record
        subnet1 = Subnet(ip_cidr='192.168.1.0/24', name='foo').add()
        subnet2 = Subnet(ip_cidr='192.168.1.128/30', name='bar').add()
        Subnet.query_with_depth()
        self.session.flush()
        # When using depth in query
        # Then I get one subnet
        self.assertEqual([subnet1], Subnet.query.filter(Subnet.depth == 0).all())
        self.assertEqual([subnet2], Subnet.query.filter(Subnet.depth == 1).all())

    def test_depth_index_ipv4(self):
        # Given a database with an existing record
        subnet1 = Subnet(ip_cidr='192.168.0.0/16', name='bar').add()
        subnet2 = Subnet(ip_cidr='192.168.0.0/24', name='bar').add()
        subnet3 = Subnet(ip_cidr='192.168.0.0/26', name='bar').add()
        subnet4 = Subnet(ip_cidr='192.168.0.64/26', name='bar').add()
        subnet5 = Subnet(ip_cidr='192.168.14.0/24', name='bar').add()
        # When listing subnet with depth
        Subnet.query_with_depth()
        self.session.flush()
        # Then depth is updated
        self.assertEqual(0, subnet1.depth)
        self.assertEqual(1, subnet2.depth)
        self.assertEqual(2, subnet3.depth)
        self.assertEqual(2, subnet4.depth)
        self.assertEqual(1, subnet5.depth)

    def test_depth_index_deleted(self):
        # Given a database with an existing record
        subnet1 = Subnet(ip_cidr='192.168.0.0/16', name='bar', status=Subnet.STATUS_DELETED).add()
        subnet2 = Subnet(ip_cidr='192.168.0.0/24', name='bar').add()
        subnet3 = Subnet(ip_cidr='192.168.0.0/26', name='bar').add()
        subnet4 = Subnet(ip_cidr='192.168.0.64/26', name='bar').add()
        subnet5 = Subnet(ip_cidr='192.168.14.0/24', name='bar').add()
        # When listing subnet with depth
        Subnet.query_with_depth()
        self.session.flush()
        # Then depth is updated
        self.assertEqual(0, subnet1.depth)
        self.assertEqual(0, subnet2.depth)
        self.assertEqual(1, subnet3.depth)
        self.assertEqual(1, subnet4.depth)
        self.assertEqual(0, subnet5.depth)

    def test_depth_index_vrf(self):
        # Given a database with an existing record
        vrf1 = Vrf(name='test1').add()
        vrf2 = Vrf(name='test2').add()
        # No VRF
        subnet1 = Subnet(ip_cidr='192.168.1.0/24', name='foo').add()
        subnet2 = Subnet(ip_cidr='192.168.1.128/30', name='bar').add()
        subnet3 = Subnet(ip_cidr='10.255.0.0/16', name='tor').add()
        subnet4 = Subnet(ip_cidr='192.0.2.23', name='fin').add()
        # VRF2
        subnet5 = Subnet(ip_cidr='2a07:6b40::/32', name='infra', vrf=vrf2).add()
        subnet6 = Subnet(ip_cidr='2a07:6b40:0::/48', name='infra-any-cast', vrf=vrf2).add()
        subnet7 = Subnet(ip_cidr='2a07:6b40:0:0::/64', name='infra-any-cast', vrf=vrf2).add()
        subnet8 = Subnet(ip_cidr='2a07:6b40:1::/48', name='all-anycast-infra-test', vrf=vrf2).add()
        # VRF1
        subnet9 = Subnet(ip_cidr='192.168.1.128/30', name='bar', vrf=vrf1).add()
        # When listing subnet with depth
        Subnet.query_with_depth()
        self.session.flush()
        # Then depth is updated
        self.assertEqual(0, subnet1.depth)
        self.assertEqual(1, subnet2.depth)
        self.assertEqual(0, subnet3.depth)
        self.assertEqual(0, subnet4.depth)
        self.assertEqual(0, subnet5.depth)
        self.assertEqual(1, subnet6.depth)
        self.assertEqual(2, subnet7.depth)
        self.assertEqual(1, subnet8.depth)
        self.assertEqual(0, subnet9.depth)

    def test_search(self):
        # Given a database with records
        Subnet(ip_cidr='192.168.1.0/24', name='foo', notes='This is a foo subnet').add()
        Subnet(ip_cidr='192.168.1.128/30', name='bar', notes='This is a bar subnet').add()
        subnet = Subnet(ip_cidr='10.0.255.0/24', name='test', notes='This a specific test subnet').add()

        # When searching for a term in notes
        records = Subnet.query.filter(Subnet._search_vector.websearch('specific')).all()
        # Then a single record is returned
        self.assertEqual(subnet, records[0])

        # When searching for a term in name
        records = Subnet.query.filter(Subnet._search_vector.websearch('test')).all()
        # Then a single record is returned
        self.assertEqual(subnet, records[0])

        # When searching for a term in ip_cidr
        records = Subnet.query.filter(Subnet._search_vector.websearch('10.0.255.0')).all()
        # Then a single record is returned
        self.assertEqual(subnet, records[0])
