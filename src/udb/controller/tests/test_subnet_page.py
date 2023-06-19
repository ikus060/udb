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
from udb.core.model import DnsZone, Subnet, Vrf

from .test_common_page import CommonTest


class SubnetTest(WebCase, CommonTest):

    base_url = 'subnet'

    obj_cls = Subnet

    new_data = {'ranges': ['192.168.0.0/24']}

    edit_data = {'ranges': ['192.168.100.0/24'], 'notes': 'test'}

    def setUp(self):
        super().setUp()
        self.vrf = Vrf(name='default').add().commit()
        self.new_data['vrf_id'] = self.vrf.id

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
            # When user transfert item to selected list and save
            available = driver.find_element('xpath', '//select[@id="dnszones-not-checked"]/option[@value="1"]')
            available.click()
            add_item_btn = driver.find_element('id', 'multiselect_rightSelected')
            add_item_btn.click()
            driver.find_element('xpath', '//select[@id="dnszones"]/option[@value="1"]')
            save_change_btn = driver.find_element('id', 'save-changes')
            save_change_btn.send_keys(Keys.ENTER)
        # Then record got updated.
        obj.expire()
        self.assertEqual([zone], obj.dnszones)

    def test_edit_invalid(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add().commit()
        # When trying to update it's name
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body={'ranges': ['invalid cidr']})
        # Then edit page is displayed with an error message
        self.assertStatus(200)
        self.assertInBody('does not appear to be a valid IPv6 or IPv4 network')

    def test_edit_with_dnszone(self):
        # Given a database with a record
        zone = DnsZone(name='examples.com').add()
        obj = self.obj_cls(ranges=['192.168.0.1/24'], dnszones=[zone], vrf=self.vrf).add().commit()
        # When editing the record
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        # Then the zone is selected
        self.assertStatus(200)
        self.assertInBody(
            'Selected    <select name="dnszones"\n            id="dnszones"\n            class="form-control"\n            size="8"\n            multiple="multiple">\n<option value="%s">examples.com</option>    </select>'
            % zone.id
        )

    def test_edit_add_dnszone(self):
        # Given a database with a record
        zone = DnsZone(name='examples.com').add().flush()
        obj = self.obj_cls(ranges=['192.168.0.1/24'], dnszones=[], vrf=self.vrf).add().commit()
        # When editing the record
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body={'dnszones': zone.id})
        self.assertStatus(303)
        # Then the zone is selected
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        self.assertStatus(200)
        self.assertInBody(
            'Selected    <select name="dnszones"\n            id="dnszones"\n            class="form-control"\n            size="8"\n            multiple="multiple">\n<option value="%s">examples.com</option>    </select>'
            % zone.id
        )

    def test_edit_with_deleted_vrf(self):
        # Given a Subnet associated to deleted VRF
        self.vrf.status = Vrf.STATUS_DELETED
        obj = self.obj_cls(ranges=['192.168.0.1/24'], dnszones=[], vrf=self.vrf).add().commit()
        # When editing the record
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        self.assertStatus(200)
        # Then the VRF Field contains our deleted VRF
        self.assertInBody('default [deleted]')

    def test_edit_assign_deleted_vrf(self):
        # Given a Subnet associated to VRF
        deleted_vrf = Vrf(name='MyVrf', status=Vrf.STATUS_DELETED).add()
        obj = self.obj_cls(ranges=['192.168.0.1/24'], dnszones=[], vrf=self.vrf).add().commit()
        # When editing the Subnet
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        self.assertStatus(200)
        # Then the deleted VRF is not listed
        self.assertNotInBody('MyVrf [deleted]')
        # When trying to assign a deleted VRF to the subnet
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body={'vrf_id': deleted_vrf.id})
        self.assertStatus(303)
        obj.expire()
        # Then the Subnet is used with the new value
        self.assertEqual(obj.vrf_id, deleted_vrf.id)
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        self.assertStatus(200)
        self.assertInBody('MyVrf [deleted]')

    def test_edit_with_deleted_zone(self):
        # Given a Subnet associated to deleted VRF
        zone = DnsZone(name='examples.com', status=DnsZone.STATUS_DELETED).add().flush()
        obj = self.obj_cls(ranges=['192.168.0.1/24'], dnszones=[zone], vrf=self.vrf).add().commit()
        # When editing the record
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        self.assertStatus(200)
        # Then the VRF Field contains our deleted VRF
        self.assertInBody('examples.com [deleted]')

    def test_edit_assign_deleted_zone(self):
        # Given a Subnet associated to VRF
        zone = DnsZone(name='examples.com').add().flush()
        deleted_zone = DnsZone(name='foo.com', status=DnsZone.STATUS_DELETED).add().flush()
        obj = self.obj_cls(ranges=['192.168.0.1/24'], dnszones=[zone], vrf=self.vrf).add().commit()
        # When editing the Subnet
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        self.assertStatus(200)
        # Then the deleted VRF is not listed
        self.assertInBody('examples.com')
        self.assertNotInBody('foo.com [deleted]')
        # When trying to assign a deleted VRF to the subnet
        self.getPage(
            url_for(self.base_url, obj.id, 'edit'), method='POST', body={'dnszones': [zone.id, deleted_zone.id]}
        )
        self.assertStatus(303)
        obj.expire()
        # Then the Subnet is used with the new value
        self.assertEqual(obj.dnszones, [zone, deleted_zone])
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        self.assertStatus(200)
        self.assertInBody('examples.com')
        self.assertInBody('foo.com [deleted]')

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
            body={'l3vni': str(value), 'l2vni': str(value), 'vlan': str(value)},
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
            body={'dhcp': new_value},
        )
        # Then object is updated.
        obj.expire()
        self.assertEqual(expected_value, obj.dhcp)

    def test_new_duplicate(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data)
        obj.add()
        obj.commit()
        # When trying to create the same record.
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=self.new_data)
        # Then error is repported to the user.
        self.assertStatus(200)
        self.assertInBody('A record already exists in database with the same value.')

    def test_depth(self):
        # Given a database with an existing record
        subnet1 = Subnet(ranges=['192.168.1.0/24'], name='foo', vrf=self.vrf, dhcp=True).add()
        subnet2 = Subnet(ranges=['192.168.1.128/30'], name='bar', vrf=self.vrf).add().commit()
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
                    'enabled',
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
                    True,
                    None,
                    '/subnet/1/edit',
                ],
                [
                    2,
                    'enabled',
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
                    False,
                    None,
                    '/subnet/2/edit',
                ],
            ],
        )

    def test_depth_index_ipv4(self):
        # Given a database with an existing record
        Subnet(ranges=['192.168.0.0/16'], name='bar1', vrf=self.vrf).add()
        Subnet(ranges=['192.168.0.0/24'], name='bar2', vrf=self.vrf).add()
        Subnet(ranges=['192.168.0.0/26'], name='bar3', vrf=self.vrf).add()
        Subnet(ranges=['192.168.0.64/26'], name='bar4', vrf=self.vrf).add()
        Subnet(ranges=['192.168.14.0/24'], name='bar5', vrf=self.vrf).add().commit()
        # When listing subnet with depth
        data = self.getJson(url_for(self.base_url, 'data.json'))
        # Then depth is updated
        self.assertEqual(
            data['data'],
            [
                [
                    1,
                    'enabled',
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
                    False,
                    None,
                    '/subnet/1/edit',
                ],
                [
                    2,
                    'enabled',
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
                    False,
                    None,
                    '/subnet/2/edit',
                ],
                [
                    3,
                    'enabled',
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
                    False,
                    None,
                    '/subnet/3/edit',
                ],
                [
                    4,
                    'enabled',
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
                    False,
                    None,
                    '/subnet/4/edit',
                ],
                [
                    5,
                    'enabled',
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
                    False,
                    None,
                    '/subnet/5/edit',
                ],
            ],
        )

    def test_depth_index_deleted(self):
        # Given a database with an existing record
        Subnet(ranges=['192.168.0.0/16'], name='bar1', vrf=self.vrf, status=Subnet.STATUS_DELETED).add()
        Subnet(ranges=['192.168.0.0/24'], name='bar2', vrf=self.vrf).add()
        Subnet(ranges=['192.168.0.0/26'], name='bar3', vrf=self.vrf).add()
        Subnet(ranges=['192.168.0.64/26'], name='bar4', vrf=self.vrf).add()
        Subnet(ranges=['192.168.14.0/24'], name='bar5', vrf=self.vrf).add().commit()
        # When listing subnet with depth
        data = self.getJson(url_for(self.base_url, 'data.json'))
        # Then depth is updated
        self.assertEqual(
            data['data'],
            [
                [
                    1,
                    'deleted',
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
                    False,
                    None,
                    '/subnet/1/edit',
                ],
                [
                    2,
                    'enabled',
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
                    False,
                    None,
                    '/subnet/2/edit',
                ],
                [
                    3,
                    'enabled',
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
                    False,
                    None,
                    '/subnet/3/edit',
                ],
                [
                    4,
                    'enabled',
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
                    False,
                    None,
                    '/subnet/4/edit',
                ],
                [
                    5,
                    'enabled',
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
                    False,
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
        Subnet(ranges=['192.168.1.0/24', '192.168.2.0/24'], name='foo', vrf=self.vrf, dnszones=[zone1, zone2]).add()
        Subnet(ranges=['192.168.1.128/30'], name='bar', vrf=self.vrf).add()
        Subnet(ranges=['10.255.0.0/16'], name='tor', vrf=self.vrf).add()
        Subnet(ranges=['192.0.2.23'], name='fin', vrf=self.vrf).add()
        # VRF2
        Subnet(ranges=['2a07:6b40::/32', '10.10.0.0/16'], name='infra', vrf=vrf2).add()
        Subnet(ranges=['2a07:6b40:0::/48'], name='infra-any-cast', vrf=vrf2).add()
        Subnet(ranges=['2a07:6b40:0:0::/64'], name='infra-any-cast', vrf=vrf2, dnszones=[zone1, zone2]).add()
        Subnet(ranges=['2a07:6b40:1::/48'], name='all-anycast-infra-test', vrf=vrf2).add()
        # VRF1
        Subnet(ranges=['192.168.1.128/30'], name='bar', vrf=vrf1).add().commit()
        # When listing subnet with depth
        data = self.getJson(url_for(self.base_url, 'data.json'))
        # Then depth is updated
        self.assertEqual(
            data['data'],
            [
                [
                    3,
                    'enabled',
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
                    False,
                    None,
                    '/subnet/3/edit',
                ],
                [
                    4,
                    'enabled',
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
                    False,
                    None,
                    '/subnet/4/edit',
                ],
                [
                    1,
                    'enabled',
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
                    False,
                    'example.com, foo.com',
                    '/subnet/1/edit',
                ],
                [
                    2,
                    'enabled',
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
                    False,
                    None,
                    '/subnet/2/edit',
                ],
                [
                    9,
                    'enabled',
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
                    False,
                    None,
                    '/subnet/9/edit',
                ],
                [
                    5,
                    'enabled',
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
                    False,
                    None,
                    '/subnet/5/edit',
                ],
                [
                    6,
                    'enabled',
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
                    False,
                    None,
                    '/subnet/6/edit',
                ],
                [
                    7,
                    'enabled',
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
                    False,
                    'example.com, foo.com',
                    '/subnet/7/edit',
                ],
                [
                    8,
                    'enabled',
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
                    False,
                    None,
                    '/subnet/8/edit',
                ],
            ],
        )
