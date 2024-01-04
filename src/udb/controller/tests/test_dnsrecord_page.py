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

from .test_common_page import CommonTest


class DnsRecordPageTest(WebCase, CommonTest):

    base_url = 'dnsrecord'

    obj_cls = DnsRecord

    new_data = {'name': 'foo.example.com', 'type': 'CNAME', 'value': 'bar.example.com'}

    edit_data = {'name': 'foo.example.com', 'type': 'CNAME', 'value': 'bar.example.com', 'notes': 'new comment'}

    def setUp(self):
        super().setUp()
        self.vrf = Vrf(name='default').add()
        self.zone = DnsZone(name='example.com').add().commit()
        all_zones = DnsZone.query.all()
        self.subnet = (
            Subnet(
                range="192.168.1.0/24",
                slave_subnets=[Subnet(range='2001:db8:85a3::/64')],
                vrf=self.vrf,
                dnszones=all_zones,
            )
            .add()
            .commit()
        )

    def test_edit_invalid(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When trying to update it's name
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body={'value': 'invalid_cname'})
        # Then edit page is displayed with an error message
        self.assertStatus(200)
        self.assertInBody('value must be a valid domain name')

    def test_edit_invalid_ip(self):
        # given a database with a record
        obj = self.obj_cls(name='foo.example.com', type='A', value='192.168.1.101').add()
        obj.commit()
        # When editing the IP address of the record for an invalid one.
        self.getPage(
            url_for(self.base_url, obj.id, 'edit'),
            method='POST',
            body={'name': 'foo.example.com', 'type': 'A', 'value': '192.168.15.101'},
        )
        # Then an error is raised
        self.assertStatus(200)
        self.assertInBody(
            'The IP address 192.168.15.101 is not allowed in the DNS zone example.com. Consider modifying the list of authorized subnets for this zone.'
        )
        # Then a link to the zone is provided with subnet name
        self.assertInBody('<a href="%s">example.com 192.168.1.0/24</a>' % url_for(self.zone, 'edit'))

    def test_edit_empty_zone(self):
        # Given a zone without any subnet
        zone1 = DnsZone(name='test.com').add().commit()
        # When trying to create a new record
        data = {'name': 'foo.test.com', 'type': 'A', 'value': '10.255.0.101'}
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=data)
        # Then an error message is raised
        self.assertStatus(200)
        self.assertInBody(
            'The IP address 10.255.0.101 is not allowed in the DNS zone test.com. Consider modifying the list of authorized subnets for this zone.'
        )
        # Then a link to the zone is provided with a zone name
        self.assertInBody('<a href="%s">test.com</a>' % url_for(zone1, 'edit'))

    def test_new_with_default(self):
        # Given a URL with default value
        self.getPage(url_for(self.base_url, 'new', **{'d-value': '192.168.34.56'}))
        # Then the page get loaded with those value
        self.assertInBody('192.168.34.56')

    def test_new_ptr_invalid(self):
        # Given an invalid PTR record.
        data = {'name': 'foo.example.com', 'type': 'PTR', 'value': 'bar.example.com'}
        # When trying to create a new record
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=data)
        # Then edit page is displayed with an error message
        self.assertStatus(200)
        self.assertInBody('PTR records must ends with `.in-addr.arpa` or `.ip6.arpa`')

    def test_new_with_default_vrf(self):
        # Given a database with a VRF
        # When creating a new DHCP Reservation without defining the VRF
        self.getPage(
            url_for(self.base_url, 'new'),
            method='POST',
            body={'name': 'foo.example.com', 'type': 'A', 'value': '192.168.1.98'},
        )
        self.assertStatus(303)
        # Then the VRF is automatically defined
        dnsrecord = DnsRecord.query.filter(DnsRecord.value == '192.168.1.98').first()
        self.assertEqual(self.vrf.id, dnsrecord.vrf_id)

    def test_new_with_invalid_vrf(self):
        # Given a database with a VRF
        vrf2 = Vrf(name='uplink').add().commit()
        # When creating a new DHCP Reservation without defining the VRF
        self.getPage(
            url_for(self.base_url, 'new'),
            method='POST',
            body={'name': 'foo.example.com', 'type': 'A', 'value': '192.168.1.98', 'vrf_id': vrf2.id},
        )
        # Then an error message is displayed
        self.assertStatus(200)
        self.assertInBody(
            "The IP address 192.168.1.98 is not allowed in the DNS zone example.com. Consider modifying the list of authorized subnets for this zone."
        )

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
        data['vrf_id'] = self.vrf.id
        # When creating a new DNS Record
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=data)
        if expect_success:
            # Then user is redirected
            self.assertStatus(303)
            # Then two records get created with the same owner
            records = DnsRecord.query.all()
            self.assertEqual(2, len(records))
            for record in records:
                self.assertIsNotNone(record.owner)
        else:
            self.assertStatus(200)
            self.assertEqual(0, DnsRecord.query.count())

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
        obj = self.obj_cls(vrf=self.vrf, **data).add()
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

    def test_new_create_reverse_record_with_error(self):
        # Given a database with a record
        Subnet(range='10.255.0.0/24', vrf=self.vrf, dnszones=[self.zone]).add().commit()
        obj = DnsRecord(name='foo.example.com', type='A', value='10.255.0.101', vrf=self.vrf).add().commit()
        self.assertIsNone(obj.get_reverse_dns_record())
        # When creating a new reverse record without proper subnet in DNS Zone
        self.getPage(url_for(obj, 'reverse_record'), method='POST')
        # Then user is redirect
        self.assertStatus(303)
        location = self.assertHeader('Location')
        self.getPage(location)
        # Then an error is displayed
        self.assertInBody('Cannnot create Reverse DNS Record.')
        self.assertInBody(
            'The IP address 10.255.0.101 is not allowed in the DNS zone in-addr.arpa. Consider modifying the list of authorized subnets for this zone.'
        )

    def test_new_create_reverse_record_with_invalid(self):
        # Given an empty database
        data = {
            'name': 'foo.invalid.com',
            'type': 'A',
            'value': '192.168.1.101',
            'create_reverse_record': 'y',
            'vrf_id': self.vrf.id,
        }
        # When creating a new DNS Record with invalid data
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=data)
        # Then error message is displayed to the user attach to the right field !
        self.assertStatus(200)
        self.assertInBody('Hostname must be defined within a valid DNS Zone.')
        # Then no records get created
        self.assertEqual(0, DnsRecord.query.count())

    def test_dns_record_mismatch_rule(self):
        # Give two DNS Record mismatch
        DnsRecord(name='foo.example.com', type='A', value='192.168.1.101', vrf=self.vrf).add().commit()
        ptr = (
            DnsRecord(name='98.1.168.192.in-addr.arpa', type='PTR', value='foo.example.com', vrf=self.vrf)
            .add()
            .commit()
        )
        # When editing PTR record
        self.getPage(url_for(ptr, 'edit'))
        self.assertStatus(200)
        # Then a warning is displayed.
        self.assertInBody(
            'PTR record must have at least one corresponding forward record with the same hostname and same IP address.'
        )

    def test_dns_record_ptr_without_forward_rule(self):
        # Given a PTR without forward record.
        ptr = (
            DnsRecord(name='98.1.168.192.in-addr.arpa', type='PTR', value='foo.example.com', vrf=self.vrf)
            .add()
            .commit()
        )
        # When editing PTR record
        self.getPage(url_for(ptr, 'edit'))
        self.assertStatus(200)
        # Then a warning is displayed.
        self.assertInBody(
            'PTR record must have at least one corresponding forward record with the same hostname and same IP address.'
        )

    def test_dns_record_ptr_with_ipv6_forward_rule(self):
        # Given a PTR without forward record.
        DnsRecord(name='foo.example.com', type='AAAA', value='2001:db8:85a3::1', vrf=self.vrf).add()
        ptr = (
            DnsRecord(name='98.1.168.192.in-addr.arpa', type='PTR', value='foo.example.com', vrf=self.vrf)
            .add()
            .commit()
        )
        # When editing PTR record
        self.getPage(url_for(ptr, 'edit'))
        self.assertStatus(200)
        # Then a warning is displayed.
        self.assertInBody(
            'PTR record must have at least one corresponding forward record with the same hostname and same IP address.'
        )

    def test_dns_cname_on_dns_zone_rule(self):
        # Given a CNAME record on dns zone
        cname = DnsRecord(name='example.com', type='CNAME', value='foo.example.com').add().commit()
        # When editing CNAME record
        self.getPage(url_for(cname, 'edit'))
        self.assertStatus(200)
        # Then a warning is displayed.
        self.assertInBody('Alias for the canonical name (CNAME) should not be defined on a DNS Zone.')
        # Then a list to conflicting DNS Zone is provided.
        zone = DnsZone.query.filter(DnsZone.name == 'example.com').first()
        self.assertInBody(url_for(zone, 'edit'))

    def test_dns_cname_not_unique_rule(self):
        # Given a CNAME and a A record on the same host
        cname = DnsRecord(name='www.example.com', type='CNAME', value='example.com').add().commit()
        other = DnsRecord(name='www.example.com', type='A', value='192.168.1.101', vrf=self.vrf).add().commit()
        # When editing CNAME record
        self.getPage(url_for(cname, 'edit'))
        self.assertStatus(200)
        # Then a warning is displayed with link to other record.
        self.assertInBody('You cannot define other record type when an alias for a canonical name (CNAME) is defined.')
        self.assertInBody(url_for(other, 'edit'))
        # When editing other record
        self.getPage(url_for(other, 'edit'))
        self.assertStatus(200)
        # Then a warning is displayed with a link to cname record.
        self.assertInBody('You cannot define other record type when an alias for a canonical name (CNAME) is defined.')
        self.assertInBody(url_for(cname, 'edit'))

    def test_dns_record_related_json(self):
        # Given two DNS with the same hostname
        fwd = DnsRecord(name='foo.example.com', type='A', value='192.168.1.101', vrf=self.vrf).add().commit()
        txt = DnsRecord(name='foo.example.com', type='TXT', value='ddzb27gl54spcr60hkpp0zzwqk2ybrwz').add().commit()
        ptr = (
            DnsRecord(name='101.1.168.192.in-addr.arpa', type='PTR', value='foo.example.com', vrf=self.vrf)
            .add()
            .commit()
        )
        # When querying list of mismatch record.
        data = self.getJson(url_for('dnsrecord', fwd.id, 'related'))
        # Then one result is returned.
        self.assertEqual(
            data,
            {
                'data': [
                    [
                        txt.id,
                        2,
                        'foo.example.com',
                        'TXT',
                        3600,
                        'ddzb27gl54spcr60hkpp0zzwqk2ybrwz',
                        'http://127.0.0.1:54583/dnsrecord/2/edit',
                    ],
                    [
                        ptr.id,
                        2,
                        '101.1.168.192.in-addr.arpa',
                        'PTR',
                        3600,
                        'foo.example.com',
                        'http://127.0.0.1:54583/dnsrecord/3/edit',
                    ],
                ]
            },
        )

    def test_dns_record_multiple_soa(self):
        # Given an existing SOA record on the DNS Zone
        record = (
            DnsRecord(
                name='example.com',
                value='ddns.bfh.info. bfh-linux-sysadmin.lists.bfh.science. 33317735 600 60 36000 3600',
                type='SOA',
            )
            .add()
            .commit()
        )
        # When trying to create a second SOA record for the same hostname
        data = {'name': 'example.com', 'type': 'SOA', 'value': 'other value'}
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=data)
        # Then an error is raised
        self.assertStatus(200)
        self.assertInBody('An SOA record already exist for this domain.')
        # Then a link to duplicate record is provided
        self.assertInBody(url_for(record, 'edit'))

    def test_dns_record_soa_without_dnszone(self):
        # Given a DnsZone
        # When creating a SOA on sub-domain
        data = {
            'name': 'foo.example.com',
            'type': 'SOA',
            'value': 'ddns.bfh.info. bfh-linux-sysadmin.lists.bfh.science. 33317735 600 60 36000 3600',
        }
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=data)
        # Then an error is raised
        self.assertStatus(200)
        self.assertInBody('SOA record must be defined on DNS Zone.')

    def test_add_a_record_without_valid_subnet(self):
        # Given a database with a Subnet and a DnsZone
        # When adding a DnsRecord
        data = {
            'name': 'foo.example.com',
            'type': 'A',
            'value': '192.0.2.23',
            'vrf_id': self.vrf.id,
        }
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=data)
        # Then an error is raised
        self.assertStatus(200)
        self.assertInBody(
            'The IP address 192.0.2.23 is not allowed in the DNS zone example.com. Consider modifying the list of authorized subnets for this zone.'
        )
        # Then a link to DNZ Zone is provided
        self.assertInBody(url_for(self.zone, 'edit'))
        # Then a list of subnet is provided matching the familly.
        self.assertInBody('192.168.1.0/24')
        self.assertNotInBody('2001:db8:85a3::/64')

    def test_add_aaaa_record_without_valid_subnet(self):
        # Given a database with a Subnet and a DnsZone
        # When adding a DnsRecord
        data = {
            'name': 'foo.example.com',
            'type': 'AAAA',
            'value': '2002::1234:abcd:ffff:c0a6:101',
            'vrf_id': self.vrf.id,
        }
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=data)
        # Then an error is raised
        self.assertStatus(200)
        self.assertInBody(
            'The IP address 2002::1234:abcd:ffff:c0a6:101 is not allowed in the DNS zone example.com. Consider modifying the list of authorized subnets for this zone.'
        )
        # Then a link to DNZ Zone is provided
        self.assertInBody(url_for(self.zone, 'edit'))
        # Then a list of subnet is provided matching the familly.
        self.assertNotInBody('192.168.1.0/24')
        self.assertInBody('2001:db8:85a3::/64')

    def test_add_ipv4_ptr_record_without_valid_dnszone(self):
        # Given a valid DNS Zone
        arpa_zone = DnsZone.query.filter(DnsZone.name == 'in-addr.arpa').first()
        # When adding a DnsRecord with invalid DNS Zone
        data = {
            'name': '255.2.0.192.in-addr.arpa',
            'type': 'PTR',
            'value': 'bar.example.com',
            'vrf_id': self.vrf.id,
        }
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=data)
        # Then an error is raised
        self.assertStatus(200)
        self.assertInBody(
            'The IP address 192.0.2.255 is not allowed in the DNS zone in-addr.arpa. Consider modifying the list of authorized subnets for this zone.'
        )
        # Then a link to DNZ Zone is provided
        self.assertInBody(url_for(arpa_zone, 'edit'))
        # Then a list of subnet is provided matching the familly.
        self.assertInBody('192.168.1.0/24')
        self.assertNotInBody('2001:db8:85a3::/64')

    def test_add_ipv6_ptr_record_without_valid_dnszone(self):
        # Given a valid DNS Zone
        arpa_zone = DnsZone.query.filter(DnsZone.name == 'ip6.arpa').first()
        # When adding a DnsRecord
        data = {
            'name': 'b.a.9.8.7.6.5.0.4.0.0.0.3.0.0.0.2.0.0.0.1.0.0.0.0.0.0.0.1.2.3.4.ip6.arpa',
            'type': 'PTR',
            'value': 'bar.example.com',
            'vrf_id': self.vrf.id,
        }
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=data)
        # Then an error is raised
        self.assertStatus(200)
        self.assertInBody(
            'The IP address 4321:0:1:2:3:4:567:89ab is not allowed in the DNS zone ip6.arpa. Consider modifying the list of authorized subnets for this zone.'
        )
        # Then a link to DNZ Zone is provided
        self.assertInBody(url_for(arpa_zone, 'edit'))
        # Then a list of subnet is provided matching the familly.
        self.assertInBody('2001:db8:85a3::/64')
        self.assertNotInBody('192.168.1.0/24')

    def test_update_parent_dnszone_name(self):
        # Given a database with a DNS Zone and a DnsRecord
        dns = DnsRecord(name='foo.example.com', type='CNAME', value='example.com').add().commit()
        # When updating the DnsZone's name
        self.getPage(url_for(self.zone, 'edit'), method='POST', body={'name': 'test.com'})
        # Then an exception is raised.
        self.assertStatus(200)
        # Make sure the constraint of dnsrecord is not shown.
        self.assertInBody("You can&#39;t change the DNS zone name once you&#39;ve created a DNS record for it.")
        self.assertInBody(url_for(dns, 'edit'))

    def test_update_parent_subnet_range_modified(self):
        # Given a database with a Subnet and a DnsRecord
        dns = DnsRecord(name='foo.example.com', type='A', value='192.168.1.25').add().commit()
        # When updating the Subnet range.
        self.getPage(
            url_for(self.subnet, 'edit'),
            method='POST',
            body={
                'dnszones': self.zone.id,
                'ranges-0-range': '192.168.1.0/30',
                'ranges-1-range': '2001:db8:85a3::/64',
            },
        )
        # Then an exception is raised.
        self.assertStatus(200)
        # Make sure the constraint of dnsrecord is shown.
        self.assertInBody(
            'Once DNS records have been created for a subnet range, it is not possible to modify this range.'
        )
        self.assertInBody(url_for(dns, 'edit'))

    def test_update_parent_subnet_range_deleted(self):
        # Given a database with a Subnet and a DnsRecord
        dns = DnsRecord(name='foo.example.com', type='AAAA', value='2001:db8:85a3::1').add().commit()
        # When updating the Subnet range. (removing secondary range)
        self.getPage(
            url_for(self.subnet, 'edit'),
            method='POST',
            body={
                'dnszones': self.zone.id,
                'ranges-0-range': '192.168.1.0/30',
            },
        )
        # Then slave subnet get soft-delete
        self.assertStatus(303)
        self.subnet.expire()
        self.assertEqual(Subnet.STATUS_DELETED, self.subnet.slave_subnets[0].status)
        # Then DNS Record get soft-delete
        dns.expire()
        self.assertEqual(DnsRecord.STATUS_DELETED, dns.estatus)

    def test_update_parent_subnet_dnszones(self):
        # Given a database with a Subnet and a DnsRecord
        dns = DnsRecord(name='foo.example.com', type='A', value='192.168.1.25').add().commit()
        # When removing the dnszone from the subnet.
        self.getPage(
            url_for(self.subnet, 'edit'),
            method='POST',
            body={'ranges-0-range': '192.168.1.0/24', 'ranges-1-range': '2001:db8:85a3::/64'},
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
                'Once DNS records have been created for a subnet, it is not possible to remove the DNS Zone associated with that subnet range.'
            )
            self.assertInBody(url_for(dns, 'edit'))

    def test_update_parent_dnszone_subnets(self):
        # Given a database with a Subnet and a DnsRecord
        dns = DnsRecord(name='foo.example.com', type='A', value='192.168.1.25').add().commit()
        # When removing the subnet from the zone.
        self.getPage(url_for(self.zone, 'edit'), method='POST', body={})
        # Then an exception is raised.
        self.assertStatus(200)
        # Make sure the constraint of dnsrecord is not shown.
        is_sqlite = 'sqlite' in str(self.session.bind)
        if is_sqlite:
            self.assertInBody('Database integrity error:')
            self.assertInBody('FOREIGN KEY constraint failed')
        else:
            self.assertInBody(
                'Once DNS records have been created for a DNS Zone, it is not possible to remove the subnet associated with that DNS Zone.'
            )
            self.assertInBody(url_for(dns, 'edit'))

    def test_update_parent_subnet_vrf(self):
        # Given another VRF
        vrf2 = Vrf(name='new').add()
        # Given a database with a Subnet and a DnsRecord
        dns = DnsRecord(name='foo.example.com', type='A', value='192.168.1.25').add().commit()
        # When removing the dnszone from the subnet.
        self.getPage(
            url_for(self.subnet, 'edit'),
            method='POST',
            body={'ranges-1-range': '192.168.1.0/24', 'vrf_id': vrf2.id, 'dnszones': self.zone.id},
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
                'Once DNS records have been created for a subnet range, it is not possible to update the VRF for this subnet.'
            )
            self.assertInBody(url_for(dns, 'edit'))

    def test_update_vrf_id(self):
        # Given a database with a second VRF
        dns = DnsRecord(name='foo.example.com', type='A', value='192.168.1.25').add().commit()
        vrf2 = Vrf(name='new')
        Subnet(
            range='192.168.1.0/24',
            vrf=vrf2,
            dnszones=[self.zone],
        ).add().commit()
        # When updating the VRF of an existing DHCP Record
        self.getPage(url_for(dns, 'edit'), method='POST', body={'vrf_id': vrf2.id})
        # Then the VRF get updated.
        self.assertStatus(303)
        dns.expire()
        self.assertEqual(dns.vrf_id, vrf2.id)
