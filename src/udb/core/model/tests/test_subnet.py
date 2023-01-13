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
        obj = Subnet(name='test', ranges=['192.168.1.0/24'], vrf=vrf).add().commit()
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
            },
        )

    def test_add_ipv4(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with IPV4
        vrf = Vrf(name='test').add()
        Subnet(vrf=vrf, ranges=['192.168.1.0/24']).add().commit()
        # Then a new record is created
        subnet = Subnet.query.first()
        self.assertEqual(1, len(subnet.ranges))
        self.assertEqual('192.168.1.0/24', subnet.ranges[0])

    def test_add_ipv6(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with IPV6
        vrf = Vrf(name='test').add()
        Subnet(vrf=vrf, ranges=['2002::1234:abcd:ffff:c0a8:101/64']).add().commit()
        # Then a new record is created
        subnet = Subnet.query.first()
        self.assertEqual(1, len(subnet.ranges))
        self.assertEqual('2002:0:0:1234::/64', subnet.ranges[0])

    def test_add_ranges(self):
        # Given an empty database
        vrf = Vrf(name='test').add()
        subnet = Subnet(vrf=vrf, ranges=['192.168.1.0/24']).add().commit()
        self.assertEqual(1, SubnetRange.query.count())
        # When adding a Subnet with IPV6
        subnet.ranges.append('192.168.12.0/24')
        subnet.add()
        subnet.commit()
        # Then a new record is created
        subnet = Subnet.query.first()
        self.assertEqual(2, SubnetRange.query.count())
        self.assertEqual(['192.168.1.0/24', '192.168.12.0/24'], subnet.ranges)

    def test_update_vrf(self):
        # Given a subnet record
        vrf1 = Vrf(name='default').add()
        vrf2 = Vrf(name='test').add()
        subnet = Subnet(vrf=vrf1, ranges=['192.168.1.0/24']).add().commit()
        self.assertEqual(1, SubnetRange.query.count())
        # When updating the VRF
        subnet.vrf = vrf2
        subnet.add()
        subnet.commit()
        # Then SubnetRange get updated too
        subnet = Subnet.query.first()
        self.assertEqual(['192.168.1.0/24'], subnet.ranges)

    def test_remove_ranges(self):
        # Given an empty database
        vrf = Vrf(name='test').add()
        subnet = Subnet(vrf=vrf, ranges=['192.168.1.0/24', '192.168.12.0/24']).add().commit()
        self.assertEqual(2, SubnetRange.query.count())
        # When adding a Subnet with IPV6
        subnet.ranges.remove('192.168.12.0/24')
        subnet.add()
        subnet.commit()
        # Then a new record is created
        self.assertEqual(1, SubnetRange.query.count())
        subnet = Subnet.query.first()
        self.assertEqual(['192.168.1.0/24'], subnet.ranges)

    @parameterized.expand(['a.168.1.0/24', '2002:k:0:1234::/64'])
    def test_invalid_ip(self, value):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with an invalid IP
        vrf = Vrf(name='test').add().commit()
        with self.assertRaises(ValueError) as cm:
            Subnet(vrf=vrf, ranges=[value]).add().commit()
        self.assertEqual(cm.exception.args, ('ranges', mock.ANY))
        # Then a record is not created
        self.assertEqual(0, Subnet.query.count())

    def test_missing_range(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet without an IP
        vrf = Vrf(name='test').add().commit()
        subnet = Subnet(vrf=vrf, name='foo')
        with self.assertRaises(ValueError):
            subnet.add().commit()
        subnet.rollback()
        # Then a record is not created
        self.assertEqual(0, Subnet.query.count())

    def test_add_with_name(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with a name
        vrf = Vrf(name='test').add()
        Subnet(vrf=vrf, ranges=['192.168.1.0/24'], name='foo').add().commit()
        # Then a new record is created
        self.assertEqual(1, Subnet.query.count())

    @parameterized.expand(['192.168.1.0/24', '2002:0:0:1234::/64'])
    def test_duplicate_ip_range(self, value):
        # Given a database with an existing record
        vrf = Vrf(name='test').add()
        Subnet(ranges=[value], name='foo', vrf=vrf).add().commit()
        self.assertEqual(1, Subnet.query.count())
        # When trying to add a Subnet with an existing ipv6_cidr
        # Then an exception is raised
        with self.assertRaises(IntegrityError):
            Subnet(ranges=[value], name='bar', vrf=vrf).add().commit()

    @parameterized.expand(['192.168.1.0/24', '2002:0:0:1234::/64'])
    def test_duplicate_cidr_with_vrf(self, value):
        # Given a database with an existing record
        vrf = Vrf(name='default')
        Subnet(name='foo', vrf=vrf, ranges=[value]).add().commit()
        self.assertEqual(1, Subnet.query.count())
        # When trying to add a Subnet with an existing IP CIDR in a different VRF
        new_vrf = Vrf(name='new vrf')
        subnet = Subnet(name='bar', vrf=new_vrf, ranges=[value]).add().commit()
        # Then subnet is created without error
        self.assertIsNotNone(subnet)
        # When trying to add a Subnet with an existing IP CIDR in same VRF
        # Then an exception is raised
        with self.assertRaises(IntegrityError):
            Subnet(name='bar', vrf=vrf, ranges=[value]).add().commit()

    def test_add_dnszonesubnet(self):
        # Given a database with an existing record
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['192.168.1.0/24'], name='foo', vrf=vrf).add().commit()
        # When trying to add an allowed subnet to the dns zone
        zone = DnsZone(name='bfh.ch').add().commit()
        subnet.dnszones.append(zone)
        zone.add().commit()
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

    def test_search(self):
        # Given a database with records
        vrf = Vrf(name='default')
        Subnet(ranges=['192.168.1.0/24'], name='foo', notes='This is a foo subnet', vrf=vrf).add()
        Subnet(ranges=['192.168.1.128/30'], name='bar', notes='This is a bar subnet', vrf=vrf).add()
        subnet = (
            Subnet(ranges=['10.0.255.0/24'], name='test', notes='This a specific test subnet', vrf=vrf).add().commit()
        )

        # When searching for a term in notes
        records = Subnet.query.filter(Subnet._search_vector.websearch('specific')).all()
        # Then a single record is returned
        self.assertEqual(subnet, records[0])

        # When searching for a term in name
        records = Subnet.query.filter(Subnet._search_vector.websearch('test')).all()
        # Then a single record is returned
        self.assertEqual(subnet, records[0])
