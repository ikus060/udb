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
from udb.core.model import DhcpRecord, Mac, Subnet, SubnetRange, Vrf


class MacTest(WebCase):
    def setUp(self):
        super().setUp()
        # Given a database with a subnet.
        self.vrf = Vrf(name='default')
        Subnet(
            subnet_ranges=[
                SubnetRange('192.0.2.0/24', dhcp=True, dhcp_start_ip='192.0.2.1', dhcp_end_ip='192.0.2.254')
            ],
            vrf=self.vrf,
        ).add().commit()

    def test_with_dhcp_record(self):
        # Given a empty database
        # When creating multiple DHCP Record with the same IP
        dhcp_record1 = DhcpRecord(ip='192.0.2.25', mac='00:00:5e:00:53:bf', vrf=self.vrf).add().commit()
        # Then a single MAC Record is created
        self.assertEqual(1, Mac.query.count())
        mac_obj = Mac.query.first()
        self.assertIn(dhcp_record1, mac_obj.related_dhcp_records)
        # And history is tracking changes
        self.assertTrue(mac_obj.messages)
        self.assertIn('related_dhcp_records', mac_obj.messages[0].changes)

    def test_mac(self):
        # Given a list of DhcpRecord and DnsRecord
        DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:bf', vrf=self.vrf).add()
        DhcpRecord(ip='192.0.2.24', mac='00:00:5e:00:53:df', vrf=self.vrf).add()
        DhcpRecord(ip='192.0.2.25', mac='00:00:5e:00:53:cf', vrf=self.vrf).add().commit()
        # When querying list of MAC
        objs = Mac.query.order_by('mac').all()
        # Then is matches the DhcpRecord.
        self.assertEqual(len(objs), 3)
        self.assertEqual(objs[0].mac, '00:00:5e:00:53:bf')
        self.assertEqual(objs[1].mac, '00:00:5e:00:53:cf')
        self.assertEqual(objs[2].mac, '00:00:5e:00:53:df')

    def test_ip_with_dhcp_deleted_status(self):
        # Given a deleted DhcpRecord
        DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:bf', status='deleted', vrf=self.vrf).add().commit()
        # When querying list of Mac
        objs = Mac.query.all()
        # Then an Ip record got created
        self.assertEqual(len(objs), 1)

    def test_get_dhcp_records(self):
        # Given a list of DnsRecords and DhcpRecord
        DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:bf', vrf=self.vrf).add().commit()
        # When querying list of related DnsRecord on a Ip.
        objs = Mac.query.order_by('mac').first().related_dhcp_records
        # Then the list include a single DnsRecord
        self.assertEqual(len(objs), 1)
        self.assertEqual(objs[0].ip, '192.0.2.23')

    def test_update_dhcp_record_ip(self):
        # Given a DhcpRecord
        record = DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:bf', vrf=self.vrf).add().commit()
        # When updating the Mac value
        record.mac = '00:00:5e:00:53:ff'
        record.commit()
        # Then a old Mac Record get update
        old_mac = Mac.query.filter(Mac.mac == '00:00:5e:00:53:bf').one()
        self.assertEqual(
            {'related_dhcp_records': [['192.0.2.23 (00:00:5e:00:53:ff)'], []]},
            old_mac.messages[-1].changes,
        )
        # Then new Mac Record get created
        new_ip = Mac.query.filter(Mac.mac == '00:00:5e:00:53:ff').one()
        self.assertEqual(
            {'mac': [None, '00:00:5e:00:53:ff'], 'related_dhcp_records': [[], ['192.0.2.23 (00:00:5e:00:53:ff)']]},
            new_ip.messages[-1].changes,
        )

    def test_update_dhcp_record_status(self):
        # Given a DhcpRecord creating an IP Record
        record = DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:bf', vrf=self.vrf).add().commit()
        Mac.query.filter(Mac.mac == '00:00:5e:00:53:bf').one()
        # When updating the DHCP Record status
        record.status = DhcpRecord.STATUS_DELETED
        record.commit()
