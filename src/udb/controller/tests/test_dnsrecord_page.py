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

from udb.controller import url_for
from udb.controller.tests import WebCase
from udb.core.model import DnsRecord, DnsZone, Subnet, Vrf

from .test_network_page import CommonTest


class DnsRecordTest(WebCase, CommonTest):

    base_url = 'dnsrecord'

    obj_cls = DnsRecord

    new_data = {'name': 'foo.example.com', 'type': 'CNAME', 'value': 'bar.example.com'}

    edit_data = {'name': 'foo.example.com', 'type': 'CNAME', 'value': 'bar.example.com', 'notes': 'new comment'}

    def setUp(self):
        super().setUp()
        vrf = Vrf(name='default').add()
        subnet = Subnet(ranges=['192.168.1.0/24', '2001:db8:85a3::/64'], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().commit()

    def test_edit_invalid(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When trying to update it's name
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body={'value': 'invalid_cname'})
        # Then edit page is displayed with an error message
        self.assertStatus(200)
        self.assertInBody('value must be a valid domain name')

    def test_new_ptr_invalid(self):
        # Given an invalid PTR record.
        data = {'name': 'foo.example.com', 'type': 'PTR', 'value': 'bar.example.com'}
        # When trying to create a new record
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=data)
        # Then edit page is displayed with an error message
        self.assertStatus(200)
        self.assertInBody('PTR records must ends with `.in-addr.arpa` or `.ip6.arpa`')

    @parameterized.expand(
        [
            ({'name': 'foo.example.com', 'type': 'A', 'value': '192.168.1.101'}, True),
            ({'name': 'foo.example.com', 'type': 'AAAA', 'value': '2001:db8:85a3::1'}, True),
            ({'name': '98.1.168.192.in-addr.arpa', 'type': 'PTR', 'value': 'bar.example.com'}, True),
            ({'name': 'foo.example.com', 'type': 'CNAME', 'value': 'bar.example.com'}, False),
        ]
    )
    def test_new_create_reverse_record(self, data, expect_success):
        # Given an empty database
        data['create_reverse_record'] = 'y'
        # When creating a new DNS Record
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=data)
        # Then user is redirected
        self.assertStatus(303)
        # Then two records get created with the same owner
        if expect_success:
            records = DnsRecord.query.all()
            self.assertEqual(2, len(records))
            for record in records:
                self.assertIsNotNone(record.owner)
        else:
            self.assertEqual(1, DnsRecord.query.count())

    @parameterized.expand(
        [
            ({'name': 'foo.example.com', 'type': 'A', 'value': '192.168.1.101'}, True),
            ({'name': 'foo.example.com', 'type': 'AAAA', 'value': '2001:db8:85a3::1'}, True),
            ({'name': '98.1.168.192.in-addr.arpa', 'type': 'PTR', 'value': 'bar.example.com'}, True),
            ({'name': 'foo.example.com', 'type': 'CNAME', 'value': 'bar.example.com'}, False),
        ]
    )
    def test_reverse_record(self, data, expect_success):
        # Given a database with a record
        obj = self.obj_cls(**data).add()
        obj.commit()
        self.assertIsNone(obj.get_reverse_dns_record())
        # When requesting reverse record to be created
        self.getPage(url_for(obj, 'reverse_record'), method='POST')
        # Then user is redirect to reverse record
        self.assertStatus(303)
        location = self.assertHeader('Location')
        # Then new record is created
        self.getPage(location)
        if expect_success:
            self.assertInBody('Reverse DNS Record created.')
            self.assertIsNotNone(obj.get_reverse_dns_record())
            self.assertIsNotNone(obj.get_reverse_dns_record().owner)
        else:
            self.assertInBody('Cannnot create Reverse DNS Record.')
            self.assertIsNone(obj.get_reverse_dns_record())

    def test_new_create_reverse_record_with_invalid(self):
        # Given an empty database
        data = {'name': 'foo.invalid.com', 'type': 'A', 'value': '192.168.1.101', 'create_reverse_record': 'y'}
        # When creating a new DNS Record with invalid data
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=data)
        # Then error message is displayed to the user attach to the right field !
        self.assertInBody('FQDN must be defined within a valid DNS Zone.')
        # Then no records get created
        self.assertEqual(0, DnsRecord.query.count())
