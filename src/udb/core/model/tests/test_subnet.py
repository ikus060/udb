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

from parameterized import parameterized
from sqlalchemy.exc import IntegrityError

from udb.controller.tests import WebCase
from udb.core.model import DnsZone, Subnet, SubnetRange, Vrf


class SubnetTest(WebCase):
    def test_json(self):
        # Given a DnsZone
        vrf = Vrf(name='default')
        obj = Subnet(name='test', ranges=['192.168.1.0/24'], vrf=vrf).add()
        # When serializing the object to json
        data = obj.to_json()
        # Then a json representation is return
        self.assertEqual(
            data,
            {
                'status': 'enabled',
                'id': 1,
                'notes': '',
                'created_at': mock.ANY,
                'modified_at': mock.ANY,
                'name': 'test',
                'ranges': ['192.168.1.0/24'],
                'vrf_id': 1,
                'l3vni': None,
                'l2vni': None,
                'vlan': None,
                'owner_id': None,
                'primary_range': '192.168.1.0/24',
            },
        )

    def test_add_ipv4(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with IPV4
        vrf = Vrf(name='test').add()
        Subnet(vrf=vrf, ranges=['192.168.1.0/24']).add()
        # Then a new record is created
        subnet = Subnet.query.first()
        self.assertEqual(['192.168.1.0/24'], subnet.ranges)

    def test_add_ipv6(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with IPV6
        vrf = Vrf(name='test').add()
        Subnet(vrf=vrf, ranges=['2002::1234:abcd:ffff:c0a8:101/64']).add()
        # Then a new record is created
        subnet = Subnet.query.first()
        self.assertEqual(['2002:0:0:1234::/64'], subnet.ranges)

    def test_add_ranges(self):
        # Given an empty database
        vrf = Vrf(name='test').add()
        subnet = Subnet(vrf=vrf, ranges=['192.168.1.0/24']).add()
        self.assertEqual(1, SubnetRange.query.count())
        # When adding a Subnet with IPV6
        subnet.ranges.append('192.168.12.0/24')
        subnet.add()
        subnet.expire()
        # Then a new record is created
        self.assertEqual(2, SubnetRange.query.count())
        self.assertEqual(['192.168.1.0/24', '192.168.12.0/24'], Subnet.query.first().ranges)

    def test_update_vrf(self):
        # Given a subnet record
        vrf1 = Vrf(name='default').add()
        vrf2 = Vrf(name='test').add()
        subnet = Subnet(vrf=vrf1, ranges=['192.168.1.0/24']).add()
        self.assertEqual(1, SubnetRange.query.count())
        # When updating the VRF
        subnet.vrf = vrf2
        subnet.add()
        # Then SubnetRange get updated too
        self.assertEqual(['192.168.1.0/24'], Subnet.query.first().ranges)

    def test_remove_ranges(self):
        # Given an empty database
        vrf = Vrf(name='test').add()
        subnet = Subnet(vrf=vrf, ranges=['192.168.1.0/24', '192.168.12.0/24']).add()
        self.assertEqual(2, SubnetRange.query.count())
        # When adding a Subnet with IPV6
        subnet.ranges.remove('192.168.12.0/24')
        subnet.add()
        subnet.expire()
        # Then a new record is created
        self.assertEqual(1, SubnetRange.query.count())
        self.assertEqual(['192.168.1.0/24'], Subnet.query.first().ranges)

    @parameterized.expand(['a.168.1.0/24', '2002:k:0:1234::/64'])
    def test_invalid_ip(self, value):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with an invalid IP
        vrf = Vrf(name='test').add()
        with self.assertRaises(ValueError) as cm:
            Subnet(vrf=vrf, ranges=[value]).add()
        self.assertEqual(cm.exception.args, ('ranges', mock.ANY))
        # Then a record is not created
        self.assertEqual(0, Subnet.query.count())

    def test_missing_range(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet without an IP
        vrf = Vrf(name='test').add()
        with self.assertRaises(ValueError):
            Subnet(vrf=vrf, name='foo').add()
        self.session.rollback()
        # Then a record is not created
        self.assertEqual(0, Subnet.query.count())

    def test_add_with_name(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with a name
        vrf = Vrf(name='test').add()
        Subnet(vrf=vrf, ranges=['192.168.1.0/24'], name='foo').add()
        # Then a new record is created
        self.assertEqual(1, Subnet.query.count())

    @parameterized.expand(['192.168.1.0/24', '2002:0:0:1234::/64'])
    def test_duplicate_ip_range(self, value):
        # Given a database with an existing record
        vrf = Vrf(name='test').add()
        Subnet(ranges=[value], name='foo', vrf=vrf).add()
        self.assertEqual(1, Subnet.query.count())
        # When trying to add a Subnet with an existing ipv6_cidr
        # Then an exception is raised
        with self.assertRaises(IntegrityError):
            Subnet(ranges=[value], name='bar', vrf=vrf).add()

    @parameterized.expand(['192.168.1.0/24', '2002:0:0:1234::/64'])
    def test_duplicate_cidr_with_vrf(self, value):
        # Given a database with an existing record
        vrf = Vrf(name='default')
        Subnet(name='foo', vrf=vrf, ranges=[value]).add()
        self.assertEqual(1, Subnet.query.count())
        # When trying to add a Subnet with an existing IP CIDR in a different VRF
        new_vrf = Vrf(name='new vrf')
        subnet = Subnet(name='bar', vrf=new_vrf, ranges=[value]).add()
        # Then subnet is created without error
        self.assertIsNotNone(subnet)
        # When trying to add a Subnet with an existing IP CIDR in same VRF
        # Then an exception is raised
        with self.assertRaises(IntegrityError):
            Subnet(name='bar', vrf=vrf, ranges=[value]).add()

    def test_add_dnszonesubnet(self):
        # Given a database with an existing record
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['192.168.1.0/24'], name='foo', vrf=vrf).add()
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

    def test_depth(self):
        # Given a database with an existing record
        vrf = Vrf(name='default')
        subnet1 = Subnet(ranges=['192.168.1.0/24'], name='foo', vrf=vrf).add()
        subnet2 = Subnet(ranges=['192.168.1.128/30'], name='bar', vrf=vrf).add()
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

    def test_depth_index_ipv4(self):
        # Given a database with an existing record
        vrf = Vrf(name='default')
        subnet1 = Subnet(ranges=['192.168.0.0/16'], name='bar', vrf=vrf).add()
        subnet2 = Subnet(ranges=['192.168.0.0/24'], name='bar', vrf=vrf).add()
        subnet3 = Subnet(ranges=['192.168.0.0/26'], name='bar', vrf=vrf).add()
        subnet4 = Subnet(ranges=['192.168.0.64/26'], name='bar', vrf=vrf).add()
        subnet5 = Subnet(ranges=['192.168.14.0/24'], name='bar', vrf=vrf).add()
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
        vrf = Vrf(name='default')
        subnet1 = Subnet(ranges=['192.168.0.0/16'], name='bar', vrf=vrf, status=Subnet.STATUS_DELETED).add()
        subnet2 = Subnet(ranges=['192.168.0.0/24'], name='bar', vrf=vrf).add()
        subnet3 = Subnet(ranges=['192.168.0.0/26'], name='bar', vrf=vrf).add()
        subnet4 = Subnet(ranges=['192.168.0.64/26'], name='bar', vrf=vrf).add()
        subnet5 = Subnet(ranges=['192.168.14.0/24'], name='bar', vrf=vrf).add()
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
        vrf = Vrf(name='default')
        vrf1 = Vrf(name='test1').add()
        vrf2 = Vrf(name='test2').add()
        # Default VRF
        subnet1 = Subnet(ranges=['192.168.1.0/24'], name='foo', vrf=vrf).add()
        subnet2 = Subnet(ranges=['192.168.1.128/30'], name='bar', vrf=vrf).add()
        subnet3 = Subnet(ranges=['10.255.0.0/16'], name='tor', vrf=vrf).add()
        subnet4 = Subnet(ranges=['192.0.2.23'], name='fin', vrf=vrf).add()
        # VRF2
        subnet5 = Subnet(ranges=['2a07:6b40::/32'], name='infra', vrf=vrf2).add()
        subnet6 = Subnet(ranges=['2a07:6b40:0::/48'], name='infra-any-cast', vrf=vrf2).add()
        subnet7 = Subnet(ranges=['2a07:6b40:0:0::/64'], name='infra-any-cast', vrf=vrf2).add()
        subnet8 = Subnet(ranges=['2a07:6b40:1::/48'], name='all-anycast-infra-test', vrf=vrf2).add()
        # VRF1
        subnet9 = Subnet(ranges=['192.168.1.128/30'], name='bar', vrf=vrf1).add()
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
        vrf = Vrf(name='default')
        Subnet(ranges=['192.168.1.0/24'], name='foo', notes='This is a foo subnet', vrf=vrf).add()
        Subnet(ranges=['192.168.1.128/30'], name='bar', notes='This is a bar subnet', vrf=vrf).add()
        subnet = Subnet(ranges=['10.0.255.0/24'], name='test', notes='This a specific test subnet', vrf=vrf).add()

        # When searching for a term in notes
        records = Subnet.query.filter(Subnet._search_vector.websearch('specific')).all()
        # Then a single record is returned
        self.assertEqual(subnet, records[0])

        # When searching for a term in name
        records = Subnet.query.filter(Subnet._search_vector.websearch('test')).all()
        # Then a single record is returned
        self.assertEqual(subnet, records[0])
