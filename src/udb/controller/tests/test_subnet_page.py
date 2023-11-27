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


from parameterized import parameterized
from selenium.webdriver.common.keys import Keys

from udb.controller import url_for
from udb.controller.tests import WebCase
from udb.core.model import DhcpRecord, DnsRecord, DnsZone, Subnet, SubnetRange, Vrf

from .test_common_page import CommonTest


class SubnetPageTest(WebCase, CommonTest):

    base_url = 'subnet'

    obj_cls = Subnet

    edit_data = {'notes': 'test', 'vlan': 3}

    def setUp(self):
        super().setUp()
        self.vrf = Vrf(name='default').add().commit()
        self.new_data = {'subnet_ranges': [SubnetRange('192.168.0.0/24')], 'vrf_id': self.vrf.id}
        self.new_post = {'subnet_ranges-0-range': '192.168.0.0/24', 'vrf_id': self.vrf.id}
        self.new_json = {
            'subnet_ranges': [{'dhcp': False, 'dhcp_end_ip': None, 'dhcp_start_ip': None, 'range': '192.168.0.0/24'}],
            'vrf_id': self.vrf.id,
        }
        self.edit_post = {'notes': 'test', 'vlan': 3, 'subnet_ranges-0-range': '192.168.0.0/24'}

    def test_edit_dnszone_selenium(self):
        # Given a database with a record
        zone = DnsZone(name='examples.com').add()
        obj = self.obj_cls(**self.new_data).add().commit()
        # Then editing that record
        with self.selenium() as driver:
            # When making a query to audit log
            driver.get(url_for(self.base_url, obj.id, 'edit'))
            # Then the web page is loaded without error.
            self.assertFalse(driver.get_log('browser'))
            # When user click on item
            available = driver.find_element('css selector', '.non-selected-wrapper a.item[data-value="%s"]' % zone.id)
            available.click()
            # Then element is transfer to selected list
            driver.find_element('css selector', '.selected-wrapper a.item[data-value="%s"]' % zone.id)
            # When saving the form
            save_change_btn = driver.find_element('id', 'save-changes')
            save_change_btn.send_keys(Keys.ENTER)
        # Then record got updated.
        obj.expire()
        self.assertEqual([zone], obj.dnszones)

    def test_edit_invalid(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add().commit()
        # When trying to update it's name
        self.getPage(
            url_for(self.base_url, obj.id, 'edit'), method='POST', body={'subnet_ranges-0-range': ['invalid cidr']}
        )
        # Then edit page is displayed with an error message
        self.assertStatus(200)
        self.assertInBody('invalid cidr is not a valid IPv4 or IPv6 range')

    def test_edit_with_dnszone(self):
        # Given a database with a record
        zone = DnsZone(name='examples.com').add()
        obj = self.obj_cls(subnet_ranges=[SubnetRange('192.168.0.1/24')], dnszones=[zone], vrf=self.vrf).add().commit()
        # When editing the record
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        # Then the zone is selected
        self.assertStatus(200)
        self.assertInBody('<option selected value="%s">' % zone.id)

    def test_edit_add_dnszone(self):
        # Given a database with a record
        zone = DnsZone(name='examples.com').add().flush()
        obj = self.obj_cls(subnet_ranges=[SubnetRange('192.168.0.1/24')], dnszones=[], vrf=self.vrf).add().commit()
        # When editing the record
        self.getPage(
            url_for(self.base_url, obj.id, 'edit'),
            method='POST',
            body={'dnszones': zone.id, 'subnet_ranges-0-range': '192.168.0.0/24'},
        )
        self.assertStatus(303)
        # Then the zone is selected
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        self.assertStatus(200)
        self.assertInBody('<option selected value="%s">' % zone.id)

    def test_edit_with_disabled_vrf(self):
        # Given a Subnet associated to deleted VRF
        self.vrf.status = Vrf.STATUS_DISABLED
        obj = self.obj_cls(subnet_ranges=[SubnetRange('192.168.0.1/24')], dnszones=[], vrf=self.vrf).add().commit()
        # When editing the record
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        self.assertStatus(200)
        # Then the VRF Field contains our deleted VRF
        self.assertInBody('default [Disabled]')

    def test_edit_assign_deleted_vrf(self):
        # Given a Subnet associated to VRF
        deleted_vrf = Vrf(name='MyVrf', status=Vrf.STATUS_DELETED).add()
        obj = self.obj_cls(subnet_ranges=[SubnetRange('192.168.0.0/24')], dnszones=[], vrf=self.vrf).add().commit()
        # When editing the Subnet
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        self.assertStatus(200)
        # Then the deleted VRF is not listed
        self.assertNotInBody('MyVrf [Deleted]')
        # When trying to assign a deleted VRF to the subnet
        self.getPage(
            url_for(self.base_url, obj.id, 'edit'),
            method='POST',
            body={'vrf_id': deleted_vrf.id, 'subnet_ranges-0-range': '192.168.0.0/24'},
        )
        self.assertStatus(303)
        obj.expire()
        # Then the Subnet is used with the new value
        self.assertEqual(obj.vrf_id, deleted_vrf.id)
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        self.assertStatus(200)
        self.assertInBody('MyVrf [Deleted]')

    def test_edit_with_disabled_zone(self):
        # Given a Subnet associated to deleted VRF
        zone = DnsZone(name='examples.com', status=DnsZone.STATUS_DISABLED).add().flush()
        obj = self.obj_cls(subnet_ranges=[SubnetRange('192.168.0.1/24')], dnszones=[zone], vrf=self.vrf).add().commit()
        # When editing the record
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        self.assertStatus(200)
        # Then the VRF Field contains our deleted VRF
        self.assertInBody('examples.com [Disabled]')

    def test_edit_assign_deleted_zone(self):
        # Given a Subnet associated to VRF
        zone = DnsZone(name='examples.com').add().flush()
        deleted_zone = DnsZone(name='foo.com', status=DnsZone.STATUS_DELETED).add().flush()
        obj = self.obj_cls(subnet_ranges=[SubnetRange('192.168.0.0/24')], dnszones=[zone], vrf=self.vrf).add().commit()
        # When editing the Subnet
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        self.assertStatus(200)
        # Then the deleted VRF is not listed
        self.assertInBody('examples.com')
        self.assertNotInBody('foo.com [Deleted]')
        # When trying to assign a deleted VRF to the subnet
        self.getPage(
            url_for(self.base_url, obj.id, 'edit'),
            method='POST',
            body={'dnszones': [zone.id, deleted_zone.id], 'subnet_ranges-0-range': '192.168.0.0/24'},
        )
        self.assertStatus(303)
        obj.expire()
        # Then the Subnet is used with the new value
        self.assertEqual(obj.dnszones, [zone, deleted_zone])
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        self.assertStatus(200)
        self.assertInBody('examples.com')
        self.assertInBody('foo.com [Deleted]')

    @parameterized.expand(
        [
            ('minus', -1, False),
            ('zero', 0, True),
            ('max', 2147483647, True),
            ('overlimit', 2147483648, False),
        ]
    )
    def test_edit_l3vni_l2vni_vlan(self, unused, value, expect_succes):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add().commit()
        # When updating l3vni, l2vni and vlan to 0
        self.getPage(
            url_for(self.base_url, obj.id, 'edit'),
            method='POST',
            body={
                'l3vni': str(value),
                'l2vni': str(value),
                'vlan': str(value),
                'subnet_ranges-0-range': '192.168.0.0/24',
            },
        )
        if expect_succes:
            # Then user is redirected
            self.assertStatus(303)
            # Then object is updated
            obj.expire()
            self.assertEqual(value, obj.l3vni)
            self.assertEqual(value, obj.l2vni)
            self.assertEqual(value, obj.vlan)
        else:
            self.assertStatus(200)
            self.assertInBody('L3VNI must be at least 0.')
            self.assertInBody('L2VNI must be at least 0.')
            self.assertInBody('VLAN must be at least 0.')

    @parameterized.expand(
        [
            ('on', True),
            ('', False),
        ]
    )
    def test_edit_dhcp_enabled(self, new_value, expected_value):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add().commit()
        # When updating DHCP
        self.getPage(
            url_for(self.base_url, obj.id, 'edit'),
            method='POST',
            body={
                'subnet_ranges-0-range': '192.168.0.0/24',
                'subnet_ranges-0-dhcp': new_value,
                'subnet_ranges-0-dhcp_start_ip': '192.168.0.1',
                'subnet_ranges-0-dhcp_end_ip': '192.168.0.100',
            },
        )
        self.assertStatus(303)
        # Then object is updated.
        obj.expire()
        self.assertEqual(expected_value, obj.subnet_ranges[0].dhcp)

    def test_edit_add_range(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add().commit()
        subnetrange_id = obj.subnet_ranges[0].id
        # Given a new subnet
        payload = {
            'subnet_ranges-0-range': obj.subnet_ranges[0].range,
            'subnet_ranges-1-range': '192.168.14.0/24',
        }
        # When creating the subnet with DHCP ranges
        self.getPage(url_for(obj, 'edit'), method='POST', body=payload)
        # Then subnet get updated
        self.assertStatus(303)
        # Then subnetrange was updated too
        obj.expire()
        self.assertEqual(subnetrange_id, obj.subnet_ranges[0].id)

    def test_edit_update_range(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add().commit()
        subnetrange_id = obj.subnet_ranges[0].id
        # Given a new subnet
        payload = {
            'subnet_ranges-0-range': '192.168.14.0/24',
        }
        # When creating the subnet with DHCP ranges
        self.getPage(url_for(obj, 'edit'), method='POST', body=payload)
        # Then subnet get updated
        self.assertStatus(303)
        # Then a new subnetrange was created
        obj.expire()
        self.assertNotEqual(subnetrange_id, obj.subnet_ranges[0].id)

    def test_edit_update_range_with_children(self):
        # Given a Subnet with Children DNS Record and DHCP Record
        zone = DnsZone(name='example.com').add()
        subnet = Subnet(dnszones=[zone], **self.new_data).add().commit()
        subnetrange_id = subnet.subnet_ranges[0].id
        DnsRecord(name='foo.example.com', type='A', value='192.168.0.25').add().commit()
        DhcpRecord(ip='192.168.0.50', mac='FF:40:23:5D:5D:9F').add().commit()
        # When editing the subnet range with a similar range.
        self.getPage(
            url_for(subnet, 'edit'),
            method='POST',
            body={
                'subnet_ranges-0-range': '192.168.0.0/22',
                'dnszones': zone.id,
            },
        )
        # Then the record get updatd without error.
        self.assertStatus(303)
        subnet.expire()
        self.assertEqual(subnetrange_id, subnet.subnet_ranges[0].id)
        self.assertEqual('192.168.0.0/22', subnet.subnet_ranges[0].range)

    def test_new_ranges(self):
        # Given a data without records
        # When creating a subnet for the first time
        self.getPage(url_for(self.base_url, 'new'))
        self.assertStatus(200)
        # The page display an empty IP Ranges to be filled by user
        self.assertInBody('DHCP Enabled')
        self.assertInBody('DHCP Start')
        self.assertInBody('DHCP Stop')
        self.assertInBody('Add row')

    def test_new_duplicate(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data)
        obj.add()
        obj.commit()
        # When trying to create the same record.
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=self.new_post)
        # Then error is repported to the user.
        self.assertStatus(200)
        self.assertInBody('This IP Range is already defined by another subnet.')
        # Then a link to the duplicate subnet is provided
        self.assertInBody(url_for(obj, 'edit'))

    def test_new_with_deleted_dnszone(self):
        # Given a dns zone enabled, disabled and deleted
        zone1 = DnsZone(name='foo.com').add().commit()
        zone2 = DnsZone(name='bar.com', status=DnsZone.STATUS_DISABLED).add().commit()
        zone3 = DnsZone(name='examples.com', status=DnsZone.STATUS_DELETED).add().commit()
        # When trying to create a new Subnet
        self.getPage(url_for(self.base_url, 'new'))
        self.assertStatus(200)
        # Then enabled zone is displayed
        self.assertInBody(zone1.name)
        # Then disabled zone is displayed with a tag
        self.assertInBody(zone2.name + ' [Disabled]')
        # Then deleted zone is hidden
        self.assertNotInBody(zone3.name)

    @parameterized.expand(
        [
            # Valid IPv4
            ('192.168.14.0/24', False, '', '', False),
            ('192.168.14.0/24', False, '192.168.14.1', '192.168.14.254', False),
            ('192.168.14.0/24', False, '192.168.14.1', '', False),
            ('192.168.14.0/24', False, '', '192.168.14.1', False),
            ('192.168.14.0/24', True, '192.168.14.1', '192.168.14.254', False),
            # Invalid out of range
            (
                '192.168.14.0/24',
                True,
                '192.168.14.0',
                '192.168.14.254',
                'DHCP start must be defined within the subnet range',
            ),
            (
                '192.168.14.0/24',
                True,
                '192.168.14.1',
                '192.168.14.255',
                'DHCP end must be defined within the subnet range',
            ),
            # Invalid with None
            (
                '192.168.14.0/24',
                True,
                '',
                '192.168.14.254',
                False,
            ),
            (
                '192.168.14.0/24',
                True,
                '192.168.14.1',
                '',
                False,
            ),
            # start > end
            (
                '192.168.14.0/24',
                True,
                '192.168.14.254',
                '192.168.14.1',
                'DHCP end must be greather than DHCP start',
            ),
            (
                '192.168.14.0/24',
                True,
                '192.168.14.100',
                '192.168.14.100',
                'DHCP end must be greather than DHCP start',
            ),
            # wrong subnet
            (
                '192.168.14.0/24',
                True,
                '192.168.15.1',
                '192.168.15.254',
                'DHCP start must be defined within the subnet range',
            ),
            # Valid IPv6
            ('2a07:6b40::/64', False, '', '', False),
            ('2a07:6b40::/64', False, '2a07:6b40::1', '2a07:6b40::ffff:ffff:ffff:ffff', False),
            ('2a07:6b40::/64', False, '2a07:6b40::1', '', False),
            ('2a07:6b40::/64', False, '', '2a07:6b40::1', False),
            ('2a07:6b40::/64', True, '2a07:6b40::1', '2a07:6b40::ffff:ffff:ffff:ffff', False),
            # Invalid with None
            ('2a07:6b40::/64', True, '', '2a07:6b40::ffff:ffff:ffff:ffff', False),
            ('2a07:6b40::/64', True, '2a07:6b40::1', '', False),
            # Invalid out of range
            (
                '2a07:6b40::/64',
                True,
                '2a07:6b40::0',
                '2a07:6b40::ffff:ffff:ffff:ffff',
                'DHCP start must be defined within the subnet range',
            ),
            # start > end
            (
                '2a07:6b40::/64',
                True,
                '2a07:6b40::ffff:ffff:ffff:ffff',
                '2a07:6b40::1',
                'DHCP end must be greather than DHCP start',
            ),
            # wrong subnet
            (
                '2a07:6b40::/64',
                True,
                '2a07:6b41::1',
                '2a07:6b40::ffff:ffff:ffff:ffff',
                'DHCP start must be defined within the subnet range',
            ),
        ]
    )
    def test_dhcp_range(self, range, dhcp_enabled, dhcp_start_ip, dhcp_end_ip, expect_error_msg):
        # Given a new subnet
        payload = {
            'name': 'My Subnet',
            'subnet_ranges-0-range': range,
            'subnet_ranges-0-dhcp': 'on' if dhcp_enabled else '',
            'subnet_ranges-0-dhcp_start_ip': dhcp_start_ip,
            'subnet_ranges-0-dhcp_end_ip': dhcp_end_ip,
            'vrf_id': self.vrf.id,
        }
        # When creating the subnet with DHCP ranges
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=payload)
        # Then we expect success or failure
        if expect_error_msg:
            self.assertStatus(200)
            self.assertInBody(expect_error_msg)
        else:
            self.assertStatus(303)

    def test_list_dhcp_enabled(self):
        # Given a subnet with multiple range with DHCP enabled
        Subnet(
            subnet_ranges=[
                SubnetRange('192.168.1.0/24', dhcp=True, dhcp_start_ip='192.168.1.1', dhcp_end_ip='192.168.1.254'),
                SubnetRange('192.168.2.0/24', dhcp=True, dhcp_start_ip='192.168.2.1', dhcp_end_ip='192.168.2.254'),
            ],
            name='foo',
            vrf=self.vrf,
        ).add().commit()
        # When querying the list of subnet
        data = self.getJson(url_for(self.base_url, 'data.json'))
        # Then DHCP value is '1' for TRUE
        self.assertEqual(
            data['data'],
            [
                [
                    1,
                    2,
                    1,
                    0,
                    '192.168.1.0/24',
                    '192.168.2.0/24',
                    'foo',
                    'default',
                    None,
                    None,
                    None,
                    None,
                    '2 on 2',
                    None,
                    '/subnet/1/edit',
                ]
            ],
        )

    def test_list_with_deleted_dns_zone(self):
        # Given a subnet associated with a deleted DNS Zone.
        zone = DnsZone(name='deleted.com', status=DnsZone.STATUS_DELETED).add()
        Subnet(
            subnet_ranges=[SubnetRange('192.168.1.0/24')],
            name='foo',
            vrf=self.vrf,
            dnszones=[zone],
        ).add().commit()
        # When displaying the list of subnet
        data = self.getJson(url_for(self.base_url, 'data.json'))
        # Then the DNS Zone name is not displayed.
        self.assertEqual(
            data['data'],
            [
                [
                    1,
                    2,
                    1,
                    0,
                    '192.168.1.0/24',
                    '',
                    'foo',
                    'default',
                    None,
                    None,
                    None,
                    None,
                    '0 on 1',
                    None,
                    '/subnet/1/edit',
                ]
            ],
        )

    def test_depth(self):
        # Given a database with an existing record
        subnet1 = Subnet(
            subnet_ranges=[
                SubnetRange('192.168.1.0/24', dhcp=True, dhcp_start_ip='192.168.1.1', dhcp_end_ip='192.168.1.254')
            ],
            name='foo',
            vrf=self.vrf,
        ).add()
        subnet2 = Subnet(subnet_ranges=[SubnetRange('192.168.1.128/30')], name='bar', vrf=self.vrf).add().commit()
        self.assertEqual(1, len(subnet1.messages))
        self.assertEqual(1, len(subnet2.messages))
        # When querying depth
        data = self.getJson(url_for(self.base_url, 'data.json'))
        # Then the depth matches the subnet indentation
        self.assertEqual(
            data['data'],
            [
                [
                    1,
                    2,
                    1,
                    0,
                    '192.168.1.0/24',
                    '',
                    'foo',
                    'default',
                    None,
                    None,
                    None,
                    None,
                    '1 on 1',
                    None,
                    '/subnet/1/edit',
                ],
                [
                    2,
                    2,
                    2,
                    1,
                    '192.168.1.128/30',
                    '',
                    'bar',
                    'default',
                    None,
                    None,
                    None,
                    None,
                    '0 on 1',
                    None,
                    '/subnet/2/edit',
                ],
            ],
        )

    def test_depth_index_ipv4(self):
        # Given a database with an existing record
        Subnet(subnet_ranges=[SubnetRange('192.168.0.0/16')], name='bar1', vrf=self.vrf).add()
        Subnet(subnet_ranges=[SubnetRange('192.168.0.0/24')], name='bar2', vrf=self.vrf).add()
        Subnet(subnet_ranges=[SubnetRange('192.168.0.0/26')], name='bar3', vrf=self.vrf).add()
        Subnet(subnet_ranges=[SubnetRange('192.168.0.64/26')], name='bar4', vrf=self.vrf).add()
        Subnet(subnet_ranges=[SubnetRange('192.168.14.0/24')], name='bar5', vrf=self.vrf).add().commit()
        # When listing subnet with depth
        data = self.getJson(url_for(self.base_url, 'data.json'))
        # Then depth is updated
        self.assertEqual(
            data['data'],
            [
                [
                    1,
                    2,
                    1,
                    0,
                    '192.168.0.0/16',
                    '',
                    'bar1',
                    'default',
                    None,
                    None,
                    None,
                    None,
                    '0 on 1',
                    None,
                    '/subnet/1/edit',
                ],
                [
                    2,
                    2,
                    2,
                    1,
                    '192.168.0.0/24',
                    '',
                    'bar2',
                    'default',
                    None,
                    None,
                    None,
                    None,
                    '0 on 1',
                    None,
                    '/subnet/2/edit',
                ],
                [
                    3,
                    2,
                    3,
                    2,
                    '192.168.0.0/26',
                    '',
                    'bar3',
                    'default',
                    None,
                    None,
                    None,
                    None,
                    '0 on 1',
                    None,
                    '/subnet/3/edit',
                ],
                [
                    4,
                    2,
                    4,
                    2,
                    '192.168.0.64/26',
                    '',
                    'bar4',
                    'default',
                    None,
                    None,
                    None,
                    None,
                    '0 on 1',
                    None,
                    '/subnet/4/edit',
                ],
                [
                    5,
                    2,
                    5,
                    1,
                    '192.168.14.0/24',
                    '',
                    'bar5',
                    'default',
                    None,
                    None,
                    None,
                    None,
                    '0 on 1',
                    None,
                    '/subnet/5/edit',
                ],
            ],
        )

    def test_depth_index_deleted(self):
        # Given a database with an existing record
        Subnet(
            subnet_ranges=[SubnetRange('192.168.0.0/16')], name='bar1', vrf=self.vrf, status=Subnet.STATUS_DELETED
        ).add()
        Subnet(subnet_ranges=[SubnetRange('192.168.0.0/24')], name='bar2', vrf=self.vrf).add()
        Subnet(subnet_ranges=[SubnetRange('192.168.0.0/26')], name='bar3', vrf=self.vrf).add()
        Subnet(subnet_ranges=[SubnetRange('192.168.0.64/26')], name='bar4', vrf=self.vrf).add()
        Subnet(subnet_ranges=[SubnetRange('192.168.14.0/24')], name='bar5', vrf=self.vrf).add().commit()
        # When listing subnet with depth
        data = self.getJson(url_for(self.base_url, 'data.json'))
        # Then depth is updated
        self.assertEqual(
            data['data'],
            [
                [
                    1,
                    0,
                    1,
                    0,
                    '192.168.0.0/16',
                    '',
                    'bar1',
                    'default',
                    None,
                    None,
                    None,
                    None,
                    '0 on 1',
                    None,
                    '/subnet/1/edit',
                ],
                [
                    2,
                    2,
                    2,
                    0,
                    '192.168.0.0/24',
                    '',
                    'bar2',
                    'default',
                    None,
                    None,
                    None,
                    None,
                    '0 on 1',
                    None,
                    '/subnet/2/edit',
                ],
                [
                    3,
                    2,
                    3,
                    1,
                    '192.168.0.0/26',
                    '',
                    'bar3',
                    'default',
                    None,
                    None,
                    None,
                    None,
                    '0 on 1',
                    None,
                    '/subnet/3/edit',
                ],
                [
                    4,
                    2,
                    4,
                    1,
                    '192.168.0.64/26',
                    '',
                    'bar4',
                    'default',
                    None,
                    None,
                    None,
                    None,
                    '0 on 1',
                    None,
                    '/subnet/4/edit',
                ],
                [
                    5,
                    2,
                    5,
                    0,
                    '192.168.14.0/24',
                    '',
                    'bar5',
                    'default',
                    None,
                    None,
                    None,
                    None,
                    '0 on 1',
                    None,
                    '/subnet/5/edit',
                ],
            ],
        )

    def test_depth_index_vrf(self):
        # Given a database with an existing record
        vrf1 = Vrf(name='test1').add()
        vrf2 = Vrf(name='test2').add()
        zone1 = DnsZone(name='example.com')
        zone2 = DnsZone(name='foo.com')
        # Default VRF
        Subnet(
            subnet_ranges=[SubnetRange('192.168.1.0/24'), SubnetRange('192.168.2.0/24')],
            name='foo',
            vrf=self.vrf,
            dnszones=[zone1, zone2],
        ).add()
        Subnet(subnet_ranges=[SubnetRange('192.168.1.128/30')], name='bar', vrf=self.vrf).add()
        Subnet(subnet_ranges=[SubnetRange('10.255.0.0/16')], name='tor', vrf=self.vrf).add()
        Subnet(subnet_ranges=[SubnetRange('192.0.2.23')], name='fin', vrf=self.vrf).add()
        # VRF2
        Subnet(subnet_ranges=[SubnetRange('2a07:6b40::/32'), SubnetRange('10.10.0.0/16')], name='infra', vrf=vrf2).add()
        Subnet(subnet_ranges=[SubnetRange('2a07:6b40:0::/48')], name='infra-any-cast', vrf=vrf2).add()
        Subnet(
            subnet_ranges=[SubnetRange('2a07:6b40:0:0::/64')], name='infra-any-cast', vrf=vrf2, dnszones=[zone1, zone2]
        ).add()
        Subnet(subnet_ranges=[SubnetRange('2a07:6b40:1::/48')], name='all-anycast-infra-test', vrf=vrf2).add()
        # VRF1
        Subnet(subnet_ranges=[SubnetRange('192.168.1.128/30')], name='bar', vrf=vrf1).add().commit()
        # When listing subnet with depth
        data = self.getJson(url_for(self.base_url, 'data.json'))
        # Then depth is updated
        self.assertEqual(
            data['data'],
            [
                [
                    3,
                    2,
                    1,
                    0,
                    '10.255.0.0/16',
                    '',
                    'tor',
                    'default',
                    None,
                    None,
                    None,
                    None,
                    '0 on 1',
                    None,
                    '/subnet/3/edit',
                ],
                [
                    4,
                    2,
                    2,
                    0,
                    '192.0.2.23/32',
                    '',
                    'fin',
                    'default',
                    None,
                    None,
                    None,
                    None,
                    '0 on 1',
                    None,
                    '/subnet/4/edit',
                ],
                [
                    1,
                    2,
                    3,
                    0,
                    '192.168.1.0/24',
                    '192.168.2.0/24',
                    'foo',
                    'default',
                    None,
                    None,
                    None,
                    None,
                    '0 on 2',
                    'example.com, foo.com',
                    '/subnet/1/edit',
                ],
                [
                    2,
                    2,
                    4,
                    1,
                    '192.168.1.128/30',
                    '',
                    'bar',
                    'default',
                    None,
                    None,
                    None,
                    None,
                    '0 on 1',
                    None,
                    '/subnet/2/edit',
                ],
                [
                    9,
                    2,
                    5,
                    0,
                    '192.168.1.128/30',
                    '',
                    'bar',
                    'test1',
                    None,
                    None,
                    None,
                    None,
                    '0 on 1',
                    None,
                    '/subnet/9/edit',
                ],
                [
                    5,
                    2,
                    6,
                    0,
                    '2a07:6b40::/32',
                    '10.10.0.0/16',
                    'infra',
                    'test2',
                    None,
                    None,
                    None,
                    None,
                    '0 on 2',
                    None,
                    '/subnet/5/edit',
                ],
                [
                    6,
                    2,
                    7,
                    1,
                    '2a07:6b40::/48',
                    '',
                    'infra-any-cast',
                    'test2',
                    None,
                    None,
                    None,
                    None,
                    '0 on 1',
                    None,
                    '/subnet/6/edit',
                ],
                [
                    7,
                    2,
                    8,
                    2,
                    '2a07:6b40::/64',
                    '',
                    'infra-any-cast',
                    'test2',
                    None,
                    None,
                    None,
                    None,
                    '0 on 1',
                    'example.com, foo.com',
                    '/subnet/7/edit',
                ],
                [
                    8,
                    2,
                    9,
                    1,
                    '2a07:6b40:1::/48',
                    '',
                    'all-anycast-infra-test',
                    'test2',
                    None,
                    None,
                    None,
                    None,
                    '0 on 1',
                    None,
                    '/subnet/8/edit',
                ],
            ],
        )
