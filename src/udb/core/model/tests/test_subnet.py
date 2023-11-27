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
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from udb.controller.tests import WebCase
from udb.core.model import DnsZone, Subnet, SubnetRange, Vrf


class SubnetTest(WebCase):
    def test_json(self):
        # Given a DnsZone
        vrf = Vrf(name='default')
        obj = (
            Subnet(
                name='test',
                subnet_ranges=[SubnetRange('192.168.1.0/24')],
                vrf=vrf,
                l3vni=1,
                l2vni=2,
                vlan=3,
                rir_status=Subnet.RIR_STATUS_ASSIGNED,
            )
            .add()
            .commit()
        )
        # When serializing the object to json
        data = obj.to_json()
        # Then a json representation is return
        self.assertEqual(
            data,
            {
                'estatus': Subnet.STATUS_ENABLED,
                'status': Subnet.STATUS_ENABLED,
                'id': 1,
                'notes': '',
                'created_at': mock.ANY,
                'modified_at': mock.ANY,
                'name': 'test',
                'ranges': ['192.168.1.0/24'],
                'vrf_id': 1,
                'vrf_estatus': 2,
                'l3vni': 1,
                'l2vni': 2,
                'vlan': 3,
                'owner_id': None,
                'rir_status': 'ASSIGNED',
                'subnet_ranges': [
                    {'dhcp': False, 'dhcp_end_ip': None, 'dhcp_start_ip': None, 'range': '192.168.1.0/24'}
                ],
            },
        )

    def test_add_ipv4(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with IPV4
        vrf = Vrf(name='test').add()
        Subnet(vrf=vrf, subnet_ranges=[SubnetRange('192.168.1.0/24')]).add().commit()
        # Then a new record is created
        subnet = Subnet.query.first()
        self.assertEqual(1, len(subnet.subnet_ranges))
        self.assertEqual('192.168.1.0/24', subnet.subnet_ranges[0].range)

    def test_add_ipv6(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with IPV6
        vrf = Vrf(name='test').add()
        Subnet(vrf=vrf, subnet_ranges=[SubnetRange('2002::1234:abcd:ffff:c0a8:101/64')]).add().commit()
        # Then a new record is created
        subnet = Subnet.query.first()
        self.assertEqual(1, len(subnet.subnet_ranges))
        self.assertEqual('2002:0:0:1234::/64', subnet.subnet_ranges[0].range)

    def test_add_with_vrf_id(self):
        # Given a VRF
        vrf = Vrf(name='test').add().commit()
        # When adding a new Subnet using vrf_id
        # Then record get created.
        Subnet(name='test', vrf_id=vrf.id, subnet_ranges=[SubnetRange('192.168.12.0/24')]).add().commit()

    def test_add_ranges(self):
        # Given an empty database
        vrf = Vrf(name='test').add()
        subnet = Subnet(vrf=vrf, subnet_ranges=[SubnetRange('192.168.1.0/24')]).add().commit()
        self.assertEqual(1, SubnetRange.query.count())
        # When adding a Subnet with IPV6
        subnet.subnet_ranges.append(SubnetRange('192.168.12.0/24'))
        subnet.add()
        subnet.commit()
        # Then a new record is created
        subnet = Subnet.query.first()
        self.assertEqual(2, SubnetRange.query.count())
        self.assertEqual(['192.168.1.0/24', '192.168.12.0/24'], [r.range for r in subnet.subnet_ranges])
        # Then a message is added to subnet
        self.assertEqual(2, len(subnet.messages))
        self.assertEqual(subnet.messages[-1].changes, {'subnet_ranges': [[], ['192.168.12.0/24']]})

    def test_remove_ranges(self):
        # Given a database with a subnet
        vrf = Vrf(name='test').add()
        subnet = (
            Subnet(vrf=vrf, subnet_ranges=[SubnetRange('192.168.1.0/24'), SubnetRange('192.168.12.0/24')])
            .add()
            .commit()
        )
        self.assertEqual(2, SubnetRange.query.count())
        # When adding a Subnet with IPV6
        subnet.subnet_ranges.pop()
        subnet.add()
        subnet.commit()
        # Then a new record is created
        self.assertEqual(1, SubnetRange.query.count())
        subnet = Subnet.query.first()
        self.assertEqual(['192.168.1.0/24'], [r.range for r in subnet.subnet_ranges])
        # Then a message is added to subnet
        self.assertEqual(2, len(subnet.messages))
        self.assertEqual(subnet.messages[-1].changes, {'subnet_ranges': [['192.168.12.0/24'], []]})

    def test_update_ranges(self):
        # Given a database with a subnet
        vrf = Vrf(name='test').add()
        subnet = (
            Subnet(vrf=vrf, subnet_ranges=[SubnetRange('192.168.0.0/24'), SubnetRange('192.168.1.0/24')]).add().commit()
        )
        self.assertEqual(2, SubnetRange.query.count())
        # When updating subnet range
        subnet.subnet_ranges[0].dhcp = True
        subnet.subnet_ranges[0].dhcp_start_ip = '192.168.0.100'
        subnet.subnet_ranges[0].dhcp_end_ip = '192.168.0.200'
        subnet.subnet_ranges[1].dhcp = True
        subnet.subnet_ranges[1].dhcp_start_ip = '192.168.1.25'
        subnet.subnet_ranges[1].dhcp_end_ip = '192.168.1.50'
        subnet.add()
        subnet.commit()
        # Then a message is added to subnet
        self.assertEqual(2, len(subnet.messages))
        self.assertEqual(
            subnet.messages[-1].changes,
            {
                'subnet_ranges': [
                    [
                        '192.168.0.0/24',
                        '192.168.1.0/24',
                    ],
                    [
                        '192.168.0.0/24 DHCP: 192.168.0.100 - 192.168.0.200',
                        '192.168.1.0/24 DHCP: 192.168.1.25 - 192.168.1.50',
                    ],
                ]
            },
        )

    def test_update_vrf(self):
        # Given a subnet record
        vrf1 = Vrf(name='default').add()
        vrf2 = Vrf(name='test').add()
        subnet = Subnet(vrf=vrf1, subnet_ranges=[SubnetRange('192.168.1.0/24')]).add().commit()
        self.assertEqual(1, SubnetRange.query.count())
        # When updating the VRF
        subnet.vrf = vrf2
        subnet.add()
        subnet.commit()
        # Then SubnetRange get updated too
        subnet = Subnet.query.first()
        self.assertEqual(['192.168.1.0/24'], [r.range for r in subnet.subnet_ranges])

    @parameterized.expand(['a.168.1.0/24', '2002:k:0:1234::/64'])
    def test_invalid_ip(self, value):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with an invalid IP
        vrf = Vrf(name='test').add().commit()
        with self.assertRaises(ValueError) as cm:
            Subnet(vrf=vrf, subnet_ranges=[SubnetRange(value)]).add().commit()
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
        Subnet(vrf=vrf, subnet_ranges=[SubnetRange('192.168.1.0/24')], name='foo').add().commit()
        # Then a new record is created
        self.assertEqual(1, Subnet.query.count())

    @parameterized.expand(['192.168.1.0/24', '2002:0:0:1234::/64'])
    def test_duplicate_ip_range(self, value):
        # Given a database with an existing record
        vrf = Vrf(name='test').add()
        Subnet(subnet_ranges=[SubnetRange(value)], name='foo', vrf=vrf).add().commit()
        self.assertEqual(1, Subnet.query.count())
        # When trying to add a Subnet with an existing ipv6_cidr
        # Then an exception is raised
        with self.assertRaises(IntegrityError):
            Subnet(subnet_ranges=[SubnetRange(value)], name='bar', vrf=vrf).add().commit()

    @parameterized.expand(['192.168.1.0/24', '2002:0:0:1234::/64'])
    def test_duplicate_cidr_with_vrf(self, value):
        # Given a database with an existing record
        vrf = Vrf(name='default')
        Subnet(name='foo', vrf=vrf, subnet_ranges=[SubnetRange(value)]).add().commit()
        self.assertEqual(1, Subnet.query.count())
        # When trying to add a Subnet with an existing IP CIDR in a different VRF
        new_vrf = Vrf(name='new vrf')
        subnet = Subnet(name='bar', vrf=new_vrf, subnet_ranges=[SubnetRange(value)]).add().commit()
        # Then subnet is created without error
        self.assertIsNotNone(subnet)
        # When trying to add a Subnet with an existing IP CIDR in same VRF
        # Then an exception is raised
        with self.assertRaises(IntegrityError):
            Subnet(name='bar', vrf=vrf, subnet_ranges=[SubnetRange(value)]).add().commit()

    def test_add_dnszonesubnet(self):
        # Given a database with an existing record
        vrf = Vrf(name='default')
        subnet = Subnet(subnet_ranges=[SubnetRange('192.168.1.0/24')], name='foo', vrf=vrf).add().commit()
        # When trying to add an allowed subnet to the dns zone
        zone = DnsZone(name='bfh.ch').add().commit()
        subnet.dnszones.append(zone)
        zone.add().commit()
        # Then a subnet is added
        subnet = Subnet.query.all()[-1]
        zone = DnsZone.query.all()[-1]
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
        Subnet(subnet_ranges=[SubnetRange('192.168.1.0/24')], name='foo', notes='This is a foo subnet', vrf=vrf).add()
        Subnet(subnet_ranges=[SubnetRange('192.168.1.128/30')], name='bar', notes='This is a bar subnet', vrf=vrf).add()
        subnet = (
            Subnet(
                subnet_ranges=[SubnetRange('10.0.255.0/24')], name='test', notes='This a specific test subnet', vrf=vrf
            )
            .add()
            .commit()
        )

        # When searching for a term in notes
        records = Subnet.query.filter(func.udb_websearch(Subnet.search_string, 'specific')).all()
        # Then a single record is returned
        self.assertEqual(subnet, records[0])

        # When searching for a term in name
        records = Subnet.query.filter(func.udb_websearch(Subnet.search_string, 'test')).all()
        # Then a single record is returned
        self.assertEqual(subnet, records[0])

    @parameterized.expand(
        [
            # Valid IPv4
            ('192.168.14.0/24', False, None, None, True),
            ('192.168.14.0/24', False, '192.168.14.1', '192.168.14.254', True),
            ('192.168.14.0/24', False, '192.168.14.1', None, True),
            ('192.168.14.0/24', False, None, '192.168.14.1', True),
            ('192.168.14.0/24', True, '192.168.14.1', '192.168.14.254', True),
            # Invalid out of range
            ('192.168.14.0/24', True, '192.168.14.0', '192.168.14.254', False),
            ('192.168.14.0/24', True, '192.168.14.1', '192.168.14.255', False),
            # Invalid with None
            ('192.168.14.0/24', True, None, '192.168.14.254', False),
            ('192.168.14.0/24', True, '192.168.14.1', None, False),
            # start > end
            ('192.168.14.0/24', True, '192.168.14.254', '192.168.14.1', False),
            # wrong subnet
            ('192.168.14.0/24', True, '192.168.15.1', '192.168.15.254', False),
            # Valid IPv6
            ('2a07:6b40::/64', False, None, None, True),
            ('2a07:6b40::/64', False, '2a07:6b40::1', '2a07:6b40::ffff:ffff:ffff:ffff', True),
            ('2a07:6b40::/64', False, '2a07:6b40::1', None, True),
            ('2a07:6b40::/64', False, None, '2a07:6b40::1', True),
            ('2a07:6b40::/64', True, '2a07:6b40::1', '2a07:6b40::ffff:ffff:ffff:ffff', True),
            # Invalid out of range
            ('2a07:6b40::/64', True, '2a07:6b40::0', '2a07:6b40::ffff:ffff:ffff:ffff', False),
            # Invalid with None
            ('2a07:6b40::/64', True, None, '2a07:6b40::ffff:ffff:ffff:ffff', False),
            ('2a07:6b40::/64', True, '2a07:6b40::1', None, False),
            # start > end
            ('2a07:6b40::/64', True, '2a07:6b40::ffff:ffff:ffff:ffff', '2a07:6b40::1', False),
            # wrong subnet
            ('2a07:6b40::/64', True, '2a07:6b41::1', '2a07:6b40::ffff:ffff:ffff:ffff', False),
        ]
    )
    def test_dhcp_range(self, range, dhcp_enabled, dhcp_start_ip, dhcp_end_ip, expect_success):
        # Given a database with records
        vrf = Vrf(name='default')
        # When creating a SubnetRange with DHCP
        subnet = Subnet(
            name='name',
            vrf=vrf,
            subnet_ranges=[
                SubnetRange(range=range, dhcp=dhcp_enabled, dhcp_start_ip=dhcp_start_ip, dhcp_end_ip=dhcp_end_ip)
            ],
        )
        # Then we expect failure or success
        if expect_success:
            subnet.add().commit()
        else:
            with self.assertRaises(IntegrityError):
                subnet.add().commit()

    def test_add_with_disabled_vrf(self):
        # Given a disabled VRF
        vrf = Vrf(name='default', status=Vrf.STATUS_DISABLED).add().commit()
        # When creating a subnet with it
        subnet = Subnet(vrf=vrf, subnet_ranges=[SubnetRange('192.168.1.0/24')]).add().commit()
        # Then the subnet get created with disabled state.
        self.assertEqual(subnet.estatus, Subnet.STATUS_DISABLED)

    def test_add_with_deleted_vrf(self):
        # Given a deleted VRF
        vrf = Vrf(name='default', status=Vrf.STATUS_DELETED).add().commit()
        # When trying to create a subnet with that VRF
        subnet = Subnet(vrf=vrf, subnet_ranges=[SubnetRange('192.168.1.0/24')]).add().commit()
        # Then the subnet get created
        self.assertEqual(subnet.estatus, Subnet.STATUS_DELETED)
