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


from unittest.mock import ANY

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
        subnets = self.app.subnet._list_query()
        # Then the depth matches the subnet indentation
        self.assertEqual(
            subnets,
            [
                {
                    'id': ANY,
                    'name': 'foo',
                    'status': 'enabled',
                    'vrf_id': 1,
                    'vrf_name': 'default',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '192.168.1.0/24',
                    'secondary_ranges': '',
                    'dnszone_names': None,
                    'order': 1,
                    'depth': 0,
                },
                {
                    'id': ANY,
                    'name': 'bar',
                    'status': 'enabled',
                    'vrf_id': 1,
                    'vrf_name': 'default',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '192.168.1.128/30',
                    'secondary_ranges': '',
                    'dnszone_names': None,
                    'order': 2,
                    'depth': 1,
                },
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
        subnets = self.app.subnet._list_query()
        # Then depth is updated
        self.assertEqual(
            subnets,
            [
                {
                    'id': ANY,
                    'name': 'bar1',
                    'status': 'enabled',
                    'vrf_id': 1,
                    'vrf_name': 'default',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '192.168.0.0/16',
                    'secondary_ranges': '',
                    'dnszone_names': None,
                    'order': 1,
                    'depth': 0,
                },
                {
                    'id': ANY,
                    'name': 'bar2',
                    'status': 'enabled',
                    'vrf_id': 1,
                    'vrf_name': 'default',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '192.168.0.0/24',
                    'secondary_ranges': '',
                    'dnszone_names': None,
                    'order': 2,
                    'depth': 1,
                },
                {
                    'id': ANY,
                    'name': 'bar3',
                    'status': 'enabled',
                    'vrf_id': 1,
                    'vrf_name': 'default',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '192.168.0.0/26',
                    'secondary_ranges': '',
                    'dnszone_names': None,
                    'order': 3,
                    'depth': 2,
                },
                {
                    'id': ANY,
                    'name': 'bar4',
                    'status': 'enabled',
                    'vrf_id': 1,
                    'vrf_name': 'default',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '192.168.0.64/26',
                    'secondary_ranges': '',
                    'dnszone_names': None,
                    'order': 4,
                    'depth': 2,
                },
                {
                    'id': ANY,
                    'name': 'bar5',
                    'status': 'enabled',
                    'vrf_id': 1,
                    'vrf_name': 'default',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '192.168.14.0/24',
                    'secondary_ranges': '',
                    'dnszone_names': None,
                    'order': 5,
                    'depth': 1,
                },
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
        subnets = self.app.subnet._list_query()
        # Then depth is updated
        self.assertEqual(
            subnets,
            [
                {
                    'id': ANY,
                    'name': 'bar1',
                    'status': 'deleted',
                    'vrf_id': 1,
                    'vrf_name': 'default',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '192.168.0.0/16',
                    'secondary_ranges': '',
                    'dnszone_names': None,
                    'order': 1,
                    'depth': 0,
                },
                {
                    'id': ANY,
                    'name': 'bar2',
                    'status': 'enabled',
                    'vrf_id': 1,
                    'vrf_name': 'default',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '192.168.0.0/24',
                    'secondary_ranges': '',
                    'dnszone_names': None,
                    'order': 2,
                    'depth': 0,
                },
                {
                    'id': ANY,
                    'name': 'bar3',
                    'status': 'enabled',
                    'vrf_id': 1,
                    'vrf_name': 'default',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '192.168.0.0/26',
                    'secondary_ranges': '',
                    'dnszone_names': None,
                    'order': 3,
                    'depth': 1,
                },
                {
                    'id': ANY,
                    'name': 'bar4',
                    'status': 'enabled',
                    'vrf_id': 1,
                    'vrf_name': 'default',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '192.168.0.64/26',
                    'secondary_ranges': '',
                    'dnszone_names': None,
                    'order': 4,
                    'depth': 1,
                },
                {
                    'id': ANY,
                    'name': 'bar5',
                    'status': 'enabled',
                    'vrf_id': 1,
                    'vrf_name': 'default',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '192.168.14.0/24',
                    'secondary_ranges': '',
                    'dnszone_names': None,
                    'order': 5,
                    'depth': 0,
                },
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
        subnets = self.app.subnet._list_query()
        # Then depth is updated
        self.assertEqual(
            subnets,
            [
                {
                    'id': ANY,
                    'name': 'tor',
                    'status': 'enabled',
                    'vrf_id': 1,
                    'vrf_name': 'default',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '10.255.0.0/16',
                    'secondary_ranges': '',
                    'dnszone_names': None,
                    'order': 1,
                    'depth': 0,
                },
                {
                    'id': ANY,
                    'name': 'fin',
                    'status': 'enabled',
                    'vrf_id': 1,
                    'vrf_name': 'default',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '192.0.2.23/32',
                    'secondary_ranges': '',
                    'dnszone_names': None,
                    'order': 2,
                    'depth': 0,
                },
                {
                    'id': ANY,
                    'name': 'foo',
                    'status': 'enabled',
                    'vrf_id': 1,
                    'vrf_name': 'default',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '192.168.1.0/24',
                    'secondary_ranges': '192.168.2.0/24',
                    'dnszone_names': 'example.com, foo.com',
                    'order': 3,
                    'depth': 0,
                },
                {
                    'id': ANY,
                    'name': 'bar',
                    'status': 'enabled',
                    'vrf_id': 1,
                    'vrf_name': 'default',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '192.168.1.128/30',
                    'secondary_ranges': '',
                    'dnszone_names': None,
                    'order': 4,
                    'depth': 1,
                },
                {
                    'id': ANY,
                    'name': 'bar',
                    'status': 'enabled',
                    'vrf_id': 2,
                    'vrf_name': 'test1',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '192.168.1.128/30',
                    'secondary_ranges': '',
                    'dnszone_names': None,
                    'order': 5,
                    'depth': 0,
                },
                {
                    'id': ANY,
                    'name': 'infra',
                    'status': 'enabled',
                    'vrf_id': 3,
                    'vrf_name': 'test2',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '2a07:6b40::/32',
                    'secondary_ranges': '10.10.0.0/16',
                    'dnszone_names': None,
                    'order': 6,
                    'depth': 0,
                },
                {
                    'id': ANY,
                    'name': 'infra-any-cast',
                    'status': 'enabled',
                    'vrf_id': 3,
                    'vrf_name': 'test2',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '2a07:6b40::/48',
                    'secondary_ranges': '',
                    'dnszone_names': None,
                    'order': 7,
                    'depth': 1,
                },
                {
                    'id': ANY,
                    'name': 'infra-any-cast',
                    'status': 'enabled',
                    'vrf_id': 3,
                    'vrf_name': 'test2',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '2a07:6b40::/64',
                    'secondary_ranges': '',
                    'dnszone_names': 'example.com, foo.com',
                    'order': 8,
                    'depth': 2,
                },
                {
                    'id': ANY,
                    'name': 'all-anycast-infra-test',
                    'status': 'enabled',
                    'vrf_id': 3,
                    'vrf_name': 'test2',
                    'l3vni': None,
                    'l2vni': None,
                    'vlan': None,
                    'primary_range': '2a07:6b40:1::/48',
                    'secondary_ranges': '',
                    'dnszone_names': None,
                    'order': 9,
                    'depth': 1,
                },
            ],
        )
