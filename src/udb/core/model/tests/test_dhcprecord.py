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
from udb.core.model import DhcpRecord, Ip, Rule, Subnet, Vrf


class DhcpRecordTest(WebCase):
    def test_json(self):
        # Given a database with a Dhcp Reservation
        vrf = Vrf(name='default')
        Subnet(
            range='2002:0000:0000:1234::/64',
            dhcp=True,
            dhcp_start_ip='2002:0000:0000:1234::0001',
            dhcp_end_ip='2002::1234:abcd:ffff:ffff:ffff',
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
            range='192.0.2.0/24',
            dhcp=True,
            dhcp_start_ip='192.0.2.1',
            dhcp_end_ip='192.0.2.254',
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
            range='2002:0:0:1234::/64',
            dhcp=True,
            dhcp_start_ip='2002:0:0:1234::0001',
            dhcp_end_ip='2002::1234:ffff:ffff:ffff:fffe',
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
            range='2001:db8:85a3::/64',
            dhcp=True,
            dhcp_start_ip='2001:db8:85a3::0001',
            dhcp_end_ip='2001:db8:85a3::ffff:ffff:fffe',
            vrf=vrf,
        ).add().commit()
        # Given a DHCP Reservation with IPv6
        DhcpRecord(ip='2001:0db8:85a3:0000:0000:8a2e:0370:7334', mac='00:00:5e:00:53:af').add().commit()
        # When querying the object
        dhcp = DhcpRecord.query.first()
        # Then the IPv6 is reformated
        self.assertEqual('2001:db8:85a3::8a2e:370:7334', dhcp.ip)

    def test_add_with_invalid_ip(self):
        # Given a database with a VRF
        Vrf(name='default').add().commit()
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
            range='192.168.2.0/24',
            dhcp=True,
            dhcp_start_ip='192.168.2.1',
            dhcp_end_ip='192.168.2.254',
            vrf=vrf,
        ).add().commit()
        self.assertEqual(0, DhcpRecord.query.count())
        # When adding a DnsRecord with invalid ip address
        with self.assertRaises(IntegrityError) as cm:
            DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:af', vrf=vrf).add().commit()
        self.assertIn('dhcprecord_subnet_required_ck', str(cm.exception))

    def test_add_with_invalid_mac(self):
        # Given an empty database
        Vrf(name='default').add().commit()
        self.assertEqual(0, DhcpRecord.query.count())
        # When adding a DnsRecord with invalid data
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DhcpRecord(ip='192.0.2.23', mac='invalid').add().commit()
        self.assertEqual(cm.exception.args, ('mac', mock.ANY))

    def test_add_with_dhcp_disabled(self):
        # Given a database with subnet with DHCP disabled
        vrf = Vrf(name='default').add()
        Subnet(range='192.0.2.0/24', dhcp=False, vrf=vrf).add().commit()
        self.assertEqual(0, DhcpRecord.query.count())
        # When adding a DnsRecord to the subnet
        # Then a record is created
        obj = DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:af').add().commit()
        # Then a soft rule is raised
        errors = Rule.verify(obj)
        self.assertEqual(1, len(errors))
        self.assertEqual('dhcprecord_invalid_subnet_rule', errors[0][0])

    def test_estatus_with_vrf_status(self):
        # Given an enabled VRF and enabled DHCP
        vrf = Vrf(name='default').add()
        Subnet(range='192.0.2.0/24', vrf=vrf).add().commit()
        record = DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:af').add().commit()
        # When deleting parent VRF.
        vrf.status = Vrf.STATUS_DELETED
        vrf.add().commit()
        # Then DHCP effective status is deleted.
        record.expire()
        self.assertEqual(DhcpRecord.STATUS_DELETED, record.estatus)
        # Then a record is created in history
        self.assertEqual(
            record.messages[-1].changes, {'subnet_estatus': [DhcpRecord.STATUS_ENABLED, DhcpRecord.STATUS_DELETED]}
        )

    def test_estatus_with_subnet_status(self):
        # Given an enabled VRF and enabled DHCP
        vrf = Vrf(name='default').add()
        subnet = Subnet(range='192.0.2.0/24', vrf=vrf).add().commit()
        record = DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:af').add().commit()
        # When deleting parent VRF.
        subnet.status = Vrf.STATUS_DELETED
        subnet.add().commit()
        # Then DHCP effective status is deleted.
        record.expire()
        self.assertEqual(DhcpRecord.STATUS_DELETED, record.estatus)
        # Then a record is created in history
        self.assertEqual(
            record.messages[-1].changes, {'subnet_estatus': [DhcpRecord.STATUS_ENABLED, DhcpRecord.STATUS_DELETED]}
        )

    def test_update_parent_subnet_range(self):
        # Given a database with a Subnet and a DHCP Record
        vrf = Vrf(name='default').add()
        subnet = Subnet(range='192.0.2.0/24', vrf=vrf).add().commit()
        DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:af').add().commit()
        # When updating the Subnet range.
        # Then an exception is raised.
        with self.assertRaises(IntegrityError) as cm:
            subnet.range = '192.0.10.0/24'
            subnet.commit()
        self.assertIn('dhcprecord_subnet_required_ck', str(cm.exception))

    def test_update_parent_subnet_vrf(self):
        # Given a database with a Subnet and a DHCP Record
        vrf = Vrf(name='default').add()
        new_vrf = Vrf(name='new').add()
        subnet = Subnet(range='192.0.2.0/24', vrf=vrf).add().commit()
        DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:af').add().commit()
        # When updating the vrf of the subnet
        # Then an exception is raised
        with self.assertRaises(IntegrityError) as cm:
            subnet.vrf = new_vrf
            subnet.add().commit()
        is_sqlite = 'sqlite' in str(self.session.bind)
        if is_sqlite:
            # SQLite doesn't return the name of the constraint.
            self.assertIn('FOREIGN KEY constraint failed', str(cm.exception))
        else:
            self.assertIn('dhcprecord_ip_fk', str(cm.exception))

    def test_deleted_record(self):
        # Given a DHCP Record
        vrf = Vrf(name='default').add()
        subnet = Subnet(range='192.0.2.0/24', vrf=vrf).add().commit()
        dhcp = DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:af').add().commit()
        # When deleting the record.
        dhcp.status = DhcpRecord.STATUS_DELETED
        dhcp.add().commit()
        # It get detached from parent.
        self.assertIsNone(dhcp._subnet)
        self.assertIsNone(dhcp.subnet_id)
        self.assertIsNone(dhcp.subnet_estatus)
        self.assertIsNone(dhcp.subnet_range)
        # Then record is still attached to IP
        self.assertIsNotNone(dhcp.vrf)
        self.assertIsNotNone(dhcp.vrf_id)
        self.assertIsNotNone(dhcp._ip)
        # Then parent could be edited without error.
        subnet.range = '10.255.0.0/24'
        subnet.add().commit()

    def test_add_with_disabled_parents(self):
        vrf = Vrf(name='default').add()
        # Given a disabled Subnet
        subnet = Subnet(range='192.0.2.0/24', vrf=vrf, status=Subnet.STATUS_DISABLED).add().commit()
        # When creating a DhcpRecord with those parent
        dhcp = DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:af').add().commit()
        # Then the record get created with disabled status.
        self.assertEqual(dhcp.estatus, dhcp.STATUS_DISABLED)
        self.assertIsNotNone(dhcp._subnet)
        self.assertIsNotNone(dhcp.subnet_id, subnet.id)

    def test_add_with_deleted_parents(self):
        vrf = Vrf(name='default').add()
        # Given a deleted Subnet
        Subnet(range='192.0.2.0/24', vrf=vrf, status=Subnet.STATUS_DELETED).add().commit()
        # When creating a DhcpRecord with those parent
        # Then an error is raised
        with self.assertRaises(IntegrityError):
            DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:af').add().commit()

    def test_dhcprecord_reassign_subnet(self):
        # Given a DHCP Record assign to a subnet
        vrf = Vrf(name='default').add()
        Subnet(range='192.168.0.0/16', vrf=vrf).add().flush()
        dhcp = DhcpRecord(ip='192.168.2.23', mac='00:00:5e:00:53:af').add().commit()
        # When creating a new Subnet
        subnet2 = Subnet(range='192.168.2.0/24', vrf=vrf).add().commit()
        # Then DHCP Record get reassigned
        dhcp.expire()
        self.assertEqual(dhcp.subnet_id, subnet2.id)
        self.assertEqual(dhcp.subnet_range, '192.168.2.0/24')
        # Then a message is added in history
        self.assertEqual(dhcp.messages[-1].changes, {'subnet_range': ['192.168.0.0/16', '192.168.2.0/24']})

    def test_update_vrf_id(self):
        # Given a DHCP Record
        vrf = Vrf(name='default').add()
        Subnet(range='192.168.0.0/16', vrf=vrf).add().flush()
        dhcp = DhcpRecord(ip='192.168.2.23', mac='00:00:5e:00:53:af').add().commit()
        # Given a database with a second VRF
        vrf2 = Vrf(name='new')
        Subnet(
            range='192.168.2.0/24',
            dhcp=True,
            dhcp_start_ip='192.168.2.1',
            dhcp_end_ip='192.168.2.254',
            vrf=vrf2,
        ).add().commit()
        # When updating the VRF of an existing DHCP Record
        dhcp.vrf = vrf2
        dhcp.add().commit()
        # Then the VRF get updated.
        dhcp.expire()
        self.assertEqual(dhcp.vrf_id, vrf2.id)

    def test_update_ip_value(self):
        # Given a DHCP Record for a specific subnet.
        # When updating the IP Value to be in a different subnet.
        vrf = Vrf(name='default').add()
        subnet1 = Subnet(range='192.168.0.0/24', vrf=vrf).add().flush()
        subnet2 = Subnet(range='192.168.1.0/24', vrf=vrf).add().commit()
        dhcp = DhcpRecord(ip='192.168.0.23', mac='00:00:5e:00:53:af').add().commit()
        self.assertEqual(subnet1.id, dhcp.subnet_id)
        # Then the record get updated.
        dhcp.ip = '192.168.1.25'
        dhcp.add().commit()
        # Then the subnet parent get updated.
        self.assertEqual(subnet2.id, dhcp.subnet_id)
