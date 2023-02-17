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
from udb.core.model import DnsZone, Subnet, Vrf

from .test_network_page import CommonTest


class SubnetTest(WebCase, CommonTest):

    base_url = 'subnet'

    obj_cls = Subnet

    new_data = {'ranges': ['192.168.0.0/24']}

    edit_data = {'ranges': ['192.168.100.0/24'], 'notes': 'test'}

    def setUp(self):
        super().setUp()
        self.vrf = Vrf(name='default').add().commit()
        self.new_data['vrf_id'] = self.vrf.id

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
            '<input class="form-check-input"  type="checkbox" name="dnszones" value="1" id="dnszones-%s" checked>'
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
            '<input class="form-check-input"  type="checkbox" name="dnszones" value="1" id="dnszones-%s" checked>'
            % zone.id
        )

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
        subnet1 = Subnet(ranges=['192.168.1.0/24'], name='foo', vrf=self.vrf).add()
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
                    '/subnet/8/edit',
                ],
            ],
        )
