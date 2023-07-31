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

from udb.controller.tests import WebCase
from udb.core.model import DhcpRecord, Ip, Rule, RuleError, Subnet, SubnetRange, Vrf


class DhcpRecordTest(WebCase):
    def test_json(self):
        # Given a database with a Dhcp Reservation
        vrf = Vrf(name='default')
        Subnet(
            subnet_ranges=[
                SubnetRange(
                    '2002:0000:0000:1234::/64',
                    dhcp=True,
                    dhcp_start_ip='2002:0000:0000:1234::0001',
                    dhcp_end_ip='2002::1234:abcd:ffff:ffff:ffff',
                )
            ],
            vrf=vrf,
        ).add().commit()
        obj = DhcpRecord(ip='2002::1234:abcd:ffff:c0a8:101', mac='00:00:5e:00:53:af').add()
        obj.commit()
        # When serializing the object to json
        data = obj.to_json()
        # Then a json representation is return
        self.assertEqual(data['ip'], '2002::1234:abcd:ffff:c0a8:101')
        self.assertEqual(data['mac'], '00:00:5e:00:53:af')

    def test_add_with_ipv4(self):
        # Given a database with subnet
        vrf = Vrf(name='default')
        Subnet(
            subnet_ranges=[
                SubnetRange(
                    '192.0.2.0/24',
                    dhcp=True,
                    dhcp_start_ip='192.0.2.1',
                    dhcp_end_ip='192.0.2.254',
                )
            ],
            vrf=vrf,
        ).add().commit()
        self.assertEqual(0, DhcpRecord.query.count())
        # When adding a DnsRecord
        DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:af').add().commit()
        # Then a new record is created
        self.assertEqual(1, DhcpRecord.query.count())
        # Then an Ip record get created
        obj = Ip.query.first()
        self.assertEqual('192.0.2.23', obj.ip)

    def test_add_with_ipv6(self):
        # Given a database with subnet
        vrf = Vrf(name='default')
        Subnet(
            subnet_ranges=[
                SubnetRange(
                    '2002:0:0:1234::/64',
                    dhcp=True,
                    dhcp_start_ip='2002:0:0:1234::0001',
                    dhcp_end_ip='2002::1234:ffff:ffff:ffff:fffe',
                )
            ],
            vrf=vrf,
        ).add().commit()
        self.assertEqual(0, DhcpRecord.query.count())
        # When adding a DnsRecord
        DhcpRecord(ip='2002::1234:abcd:ffff:c0a8:101', mac='00:00:5e:00:53:af').add().commit()
        # Then a new record is created
        self.assertEqual(1, DhcpRecord.query.count())
        # Then an Ip record get created
        obj = Ip.query.first()
        self.assertEqual('2002::1234:abcd:ffff:c0a8:101', obj.ip)

    def test_norm_ipv6(self):
        # Given a database with subnet
        vrf = Vrf(name='default')
        Subnet(
            subnet_ranges=[
                SubnetRange(
                    '2001:db8:85a3::/64',
                    dhcp=True,
                    dhcp_start_ip='2001:db8:85a3::0001',
                    dhcp_end_ip='2001:db8:85a3::ffff:ffff:fffe',
                )
            ],
            vrf=vrf,
        ).add().commit()
        # Given a DHCP Reservation with IPv6
        DhcpRecord(ip='2001:0db8:85a3:0000:0000:8a2e:0370:7334', mac='00:00:5e:00:53:af').add().commit()
        # When querying the object
        dhcp = DhcpRecord.query.first()
        # Then the IPv6 is reformated
        self.assertEqual('2001:db8:85a3::8a2e:370:7334', dhcp.ip)

    def test_add_with_invalid_ip(self):
        # Given an empty database
        self.assertEqual(0, DhcpRecord.query.count())
        # When adding a DnsRecord with invalid data
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DhcpRecord(ip='a.0.2.23', mac='00:00:5e:00:53:af').add().commit()
        self.assertEqual(cm.exception.args, ('ip', mock.ANY))

    def test_add_with_invalid_subnet(self):
        # Given a database with subnet
        vrf = Vrf(name='default')
        Subnet(
            subnet_ranges=[
                SubnetRange(
                    '192.168.2.0/24',
                    dhcp=True,
                    dhcp_start_ip='192.168.2.1',
                    dhcp_end_ip='192.168.2.254',
                )
            ],
            vrf=vrf,
        ).add().commit()
        self.assertEqual(0, DhcpRecord.query.count())
        # When adding a DnsRecord with invalid ip address
        record = DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:af').add().commit()
        # Then an exception is raised by Soft Rule
        with self.assertRaises(RuleError) as cm:
            Rule.verify(record, errors='raise')
        self.assertEqual(cm.exception.field, 'ip')

    def test_add_with_invalid_mac(self):
        # Given an empty database
        self.assertEqual(0, DhcpRecord.query.count())
        # When adding a DnsRecord with invalid data
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DhcpRecord(ip='192.0.2.23', mac='invalid').add().commit()
        self.assertEqual(cm.exception.args, ('mac', mock.ANY))

    def test_add_with_dhcp_disabled(self):
        # Given a database with subnet with DHCP disabled
        vrf = Vrf(name='default')
        Subnet(subnet_ranges=[SubnetRange('192.0.2.0/24', dhcp=False)], vrf=vrf).add().commit()
        self.assertEqual(0, DhcpRecord.query.count())
        # When adding a DnsRecord to the subnet
        # Then a record is created
        obj = DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:af').add().commit()
        # Then a soft rule is raised
        errors = Rule.verify(obj)
        self.assertEqual(1, len(errors))
