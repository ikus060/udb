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


from udb.controller import url_for
from udb.controller.tests import WebCase
from udb.core.model import DhcpRecord, Subnet, SubnetRange, User, Vrf

from .test_common_page import CommonTest


class DhcpRecordPageTest(WebCase, CommonTest):

    base_url = 'dhcprecord'

    obj_cls = DhcpRecord

    new_data = {'ip': '1.2.3.4', 'mac': '02:42:d7:e4:aa:58'}

    edit_data = {'ip': '1.2.3.5', 'mac': '02:42:d7:e4:aa:67'}

    def setUp(self):
        super().setUp()
        # Generate a changes
        self.vrf = Vrf(name='default')
        self.subnet = (
            Subnet(
                subnet_ranges=[
                    SubnetRange(
                        '1.2.3.0/24',
                        dhcp=True,
                        dhcp_start_ip='1.2.3.1',
                        dhcp_end_ip='1.2.3.254',
                    )
                ],
                vrf=self.vrf,
            )
            .add()
            .commit()
        )
        # Update data
        self.new_data['vrf_id'] = self.vrf.id

    def test_new_duplicate(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data)
        obj.add()
        obj.commit()
        # When trying to create the same record.
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=self.new_data)
        # Then error is repported to the user.
        self.assertStatus(200)
        self.assertInBody('A DHCP Reservation already exists for this MAC address.')
        # Then a link to duplicate record is provided
        self.assertInBody(url_for(obj, 'edit'))

    def test_new_with_default_vrf(self):
        # Given a database with a VRF
        # When creating a new DHCP Reservation without defining the VRF
        self.getPage(url_for(self.base_url, 'new'), method='POST', body={'ip': '1.2.3.4', 'mac': '02:42:d7:e4:aa:58'})
        self.assertStatus(303)
        # Then the VRF is automatically defined
        dhcp = DhcpRecord.query.filter(DhcpRecord.ip == '1.2.3.4').first()
        self.assertEqual(self.vrf.id, dhcp.vrf_id)

    def test_new_with_invalid_vrf(self):
        # Given a database with a VRF
        vrf2 = Vrf(name='invalid').add().commit()
        # When creating a new DHCP Reservation without defining the VRF
        self.getPage(
            url_for(self.base_url, 'new'),
            method='POST',
            body={'ip': '1.2.3.4', 'mac': '02:42:d7:e4:aa:58', 'vrf_id': vrf2.id},
        )
        # Then an error message is displayed
        self.assertStatus(200)
        self.assertInBody("The IP address 1.2.3.4 is not allowed in any subnet.")

    def test_new_with_deleted_subnet(self):
        # Given a deleted subnet
        self.subnet.status = Subnet.STATUS_DELETED
        self.subnet.add().commit()
        # When trying to create a DHCP Record
        self.getPage(
            url_for(self.base_url, 'new'),
            method='POST',
            body={'ip': '1.2.3.4', 'mac': '02:42:d7:e4:aa:58'},
        )
        # Then an error is raised.
        self.assertStatus(200)
        self.assertInBody('The IP address 1.2.3.4 is not allowed in any subnet.')

    def test_edit_owner_and_notes(self):
        # Given a database with a record
        user_obj = User.query.first()
        obj = self.obj_cls(**self.new_data)
        obj.add()
        obj.commit()
        self.assertEqual(1, len(obj.messages))
        obj.expire()
        # When editing notes and owner
        self.getPage(
            url_for(self.base_url, obj.id, 'edit'),
            method='POST',
            body={'notes': 'Change me to get notification !', 'owner': user_obj.id},
        )
        self.assertStatus(303)
        # Then a single message is added to the record
        self.assertEqual(2, len(obj.messages))

    def test_dhcprecord_new_invalid_subnet_rule(self):
        # Given a subnet with DHCP Disabled.
        subnet = Subnet.query.first()
        subnet.subnet_ranges[0].dhcp = False
        subnet.add().commit()
        # When creating a DHCP Reservation.
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=self.new_data)
        self.assertStatus(303)
        # Then user is redirect to edit page
        location = self.assertHeader('Location')
        self.assertIn('edit', location)
        # Then record got created
        self.getPage(location)
        self.assertStatus(200)
        self.assertInBody('Record created successfully.')
        # Then a warning is displayed.
        self.assertInBody('The subnet for this DHCP is currently disabled.')

    def test_dhcprecord_edit_invalid_subnet_rule(self):
        # Given a DHCP reservation on a subnet.
        record = DhcpRecord(ip='1.2.3.4', mac='02:42:d7:e4:aa:67', vrf=self.vrf).add().commit()
        # Given DHCP get disable on the subnet
        subnet = Subnet.query.first()
        subnet.subnet_ranges[0].dhcp = False
        subnet.add().commit()
        # When editing the DHCP reservation.
        self.getPage(url_for(record, 'edit'))
        self.assertStatus(200)
        # Then a warning is displayed.
        self.assertInBody('The subnet for this DHCP is currently disabled.')

    def test_dhcprecord_unique_ip(self):
        # Given two (2) dhcp reservation with the same IP.
        record1 = DhcpRecord(ip='1.2.3.4', mac='02:42:d7:e4:aa:67', vrf=self.vrf).add().commit()
        record2 = DhcpRecord(ip='1.2.3.4', mac='02:42:d7:e4:aa:58', vrf=self.vrf).add().commit()
        # When editing record
        self.getPage(url_for(record1, 'edit'))
        self.assertStatus(200)
        # Then a warning is displayed
        self.assertInBody('Multiple DHCP Reservation for the same IP address within the same VRF.')
        # When editing record
        self.getPage(url_for(record2, 'edit'))
        self.assertStatus(200)
        # Then a warning is displayed
        self.assertInBody('Multiple DHCP Reservation for the same IP address within the same VRF.')

    def test_update_parent_subnet_range_deleted(self):
        # Given a database with a Subnet and a DnsRecord
        dhcp = DhcpRecord(ip='1.2.3.4', mac='00:00:5e:00:53:af').add().commit()
        # When updating the Subnet range.
        self.getPage(
            url_for(self.subnet, 'edit'),
            method='POST',
            body={
                'subnet_ranges-0-range': '192.168.0.0/24',
                'subnet_ranges-0-dhcp': 'on',
                'subnet_ranges-0-dhcp_start_ip': '192.168.0.5',
                'subnet_ranges-0-dhcp_end_ip': '192.168.0.150',
            },
        )
        # Then an exception is raised.
        self.assertStatus(200)
        # Make sure the constraint of dnsrecord is not shown.
        is_sqlite = 'sqlite' in str(self.session.bind)
        if is_sqlite:
            self.assertInBody('Database integrity error:')
            self.assertInBody('FOREIGN KEY constraint failed')
        else:
            self.assertInBody(
                'Once DHCP reservation have been created for a subnet range, it is not possible to remove that range.'
            )
            # Then a link to the related DHCP Record is provided.
            self.assertInBody(url_for(dhcp, 'edit'))

    def test_update_parent_subnet_range_modified(self):
        # Given a database with a Subnet and a DnsRecord
        dhcp = DhcpRecord(ip='1.2.3.4', mac='00:00:5e:00:53:af').add().commit()
        # When updating the Subnet range.
        self.getPage(
            url_for(self.subnet, 'edit'),
            method='POST',
            body={
                'subnet_ranges-0-range': '1.2.3.0/30',
                'subnet_ranges-0-dhcp': 'on',
                'subnet_ranges-0-dhcp_start_ip': '1.2.3.1',
                'subnet_ranges-0-dhcp_end_ip': '1.2.3.2',
            },
        )
        # Then an exception is raised.
        self.assertStatus(200)
        # Make sure the constraint of dnsrecord is not shown.
        self.assertInBody(
            'Once DHCP reservation have been created for a subnet range, it is not possible to modify that range.'
        )
        # Then a link to the related DHCP Record is provided.
        self.assertInBody(url_for(dhcp, 'edit'))

    def test_update_parent_subnet_vrf(self):
        # Given a database with a Subnet and a DHCP Record
        new_vrf = Vrf(name='new').add().commit()
        dhcp = DhcpRecord(ip='1.2.3.23', mac='00:00:5e:00:53:af').add().commit()
        # When updating the vrf of the subnet
        self.getPage(
            url_for(self.subnet, 'edit'),
            method='POST',
            body={
                'subnet_ranges-0-range': '1.2.3.0/24',
                'subnet_ranges-0-dhcp': 'on',
                'subnet_ranges-0-dhcp_start_ip': '1.2.3.1',
                'subnet_ranges-0-dhcp_end_ip': '1.2.3.254',
                'vrf_id': new_vrf.id,
            },
        )
        # Then an exception is raised
        self.assertStatus(200)
        is_sqlite = 'sqlite' in str(self.session.bind)
        if is_sqlite:
            self.assertInBody('Database integrity error:')
            self.assertInBody('FOREIGN KEY constraint failed')
        else:
            self.assertInBody(
                'Once DHCP reservation have been created for a subnet, it is not possible to update the VRF for this subnet.'
            )
            # Then a link to the related DHCP Record is provided.
            self.assertInBody(url_for(dhcp, 'edit'))

    def test_update_vrf_id(self):
        # Given a database with a second VRF
        dhcp = DhcpRecord(ip='1.2.3.4', mac='00:00:5e:00:53:af').add().commit()
        vrf2 = Vrf(name='new')
        Subnet(
            subnet_ranges=[
                SubnetRange(
                    '1.2.3.0/24',
                    dhcp=True,
                    dhcp_start_ip='1.2.3.1',
                    dhcp_end_ip='1.2.3.254',
                )
            ],
            vrf=vrf2,
        ).add().commit()
        # When updating the VRF of an existing DHCP Record
        self.getPage(url_for(dhcp, 'edit'), method='POST', body={'vrf_id': vrf2.id})
        # Then the VRF get updated.
        self.assertStatus(303)
        dhcp.expire()
        self.assertEqual(dhcp.vrf_id, vrf2.id)
