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

from parameterized import parameterized

from udb.controller.tests import WebCase
from udb.core.model import DnsRecord, DnsZone, Subnet, Vrf


class DnsRecordTest(WebCase):
    def test_json(self):
        # Given a DnsRecord
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['192.0.2.0/24'], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        obj = DnsRecord(name='foo.example.com', type='A', value='192.0.2.23').add().commit()
        # When serializing the object to json
        data = obj.to_json()
        # Then a json representation is return
        self.assertEqual(data['name'], 'foo.example.com')
        self.assertEqual(data['type'], 'A')
        self.assertEqual(data['ttl'], 3600)
        self.assertEqual(data['value'], '192.0.2.23')

    @parameterized.expand(
        [
            (
                {'name': 'foo.example.com', 'type': 'A', 'value': '192.168.1.101'},
                '192.168.1.101',
                'foo.example.com',
            ),
            (
                {'name': 'foo.example.com', 'type': 'AAAA', 'value': '2001:db8::1'},
                '2001:db8::1',
                'foo.example.com',
            ),
            (
                {'name': '98.1.168.192.in-addr.arpa', 'type': 'PTR', 'value': 'bar.example.com'},
                '192.168.1.98',
                'bar.example.com',
            ),
            (
                {
                    'name': '1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.8.b.d.0.1.0.0.2.ip6.arpa',
                    'type': 'PTR',
                    'value': 'bar.example.com',
                },
                '2001:db8::1',
                'bar.example.com',
            ),
            (
                {
                    'name': 'b.a.9.8.7.6.5.0.4.0.0.0.3.0.0.0.2.0.0.0.1.0.0.0.0.0.0.0.1.2.3.4.ip6.arpa',
                    'type': 'PTR',
                    'value': 'bar.example.com',
                },
                '4321:0:1:2:3:4:567:89ab',
                'bar.example.com',
            ),
            (
                {'name': 'foo.example.com', 'type': 'CNAME', 'value': 'bar.example.com'},
                None,
                'foo.example.com',
            ),
        ]
    )
    def test_ip_and_hostname_value(self, data, expected_ip_value, expected_hostname_value):
        # Given a Vrf, Subnet and DnsZone
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['192.168.1.0/24', '2001:db8::/64', '4321:0:1:2:3:4:567:0/112'], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        # When creating a DnsRecord
        record = DnsRecord(**data).add().commit()
        # Then validate ip_value
        self.assertEqual(expected_ip_value, record.ip_value)
        self.assertEqual(expected_hostname_value, record.hostname_value)
        # When using ip to make a query a record is returned
        DnsRecord.query.filter(DnsRecord.generated_ip == expected_ip_value).one()
        # When using hostname_value to make a query a record is returned
        DnsRecord.query.filter(DnsRecord.hostname_value == expected_hostname_value).one()

    def test_add_without_type(self):
        with self.assertRaises(ValueError):
            DnsRecord(name='foo.example.com', value='192.0.2.23').add().commit()

    def test_add_a_record(self):
        # Given a database with a subnet and a dnszone
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['192.0.2.0/24'], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord
        DnsRecord(name='foo.example.com', type='A', value='192.0.2.23').add().commit()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    def test_add_a_record_with_invalid_value(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='A', value='invalid').add().commit()
        self.assertEqual(cm.exception.args, ('value', mock.ANY))

    def test_add_a_record_without_valid_dnszone(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='A', value='192.0.2.23').add().commit()
        self.assertEqual(cm.exception.args, ('name', mock.ANY))

    def test_add_a_record_without_valid_subnet(self):
        # Given a database with a Subnet and a DnsZone
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['10.255.0.0/16'], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        # When adding a DnsRecord
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='A', value='192.0.2.23').add().commit()
        self.assertEqual(cm.exception.args, ('value', mock.ANY))

    def test_add_aaaa_record(self):
        # Given an empty database
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['2002:0:0:1234::/64'], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        # When adding a DnsRecord
        DnsRecord(name='foo.example.com', type='AAAA', value='2002::1234:abcd:ffff:c0a9:101').add().commit()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    def test_add_aaaa_norm_ipv6(self):
        # Given a DNS Record created with leading zero
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['2001:db8:85a3::/64'], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        DnsRecord(name='foo.example.com', type='AAAA', value='2001:0db8:85a3:0000:0000:8a2e:0370:7334').add().commit()
        # When querying the record
        dns = DnsRecord.query.first()
        # Then the IP Address is compressed
        self.assertEqual('2001:db8:85a3::8a2e:370:7334', dns.value)

    def test_add_aaaa_record_with_invalid_value(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='AAAA', value='invalid').add().commit()
        self.assertEqual(cm.exception.args, ('value', mock.ANY))

    def test_add_aaaa_record_without_valid_dnszone(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord
        # Then an error is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='AAAA', value='2002::1234:abcd:ffff:c0a7:101').add().commit()
        self.assertEqual(cm.exception.args, ('name', mock.ANY))

    def test_add_aaaa_record_without_valid_subnet(self):
        # Given a database with a valid DNSZone
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['10.0.0.0/8'], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        # When adding a DnsRecord
        # Then an error is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='AAAA', value='2002::1234:abcd:ffff:c0a6:101').add().commit()
        self.assertEqual(cm.exception.args, ('value', mock.ANY))

    def test_add_cname_record(self):
        # Given a DnsZone
        DnsZone(name='example.com').add().flush()
        # When adding a DnsRecord
        DnsRecord(name='foo.example.com', type='CNAME', value='bar.example.com').add().commit()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    def test_add_cname_record_with_invalid_value(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='CNAME', value='192.0.2.23').add().commit()
        self.assertEqual(cm.exception.args, ('value', mock.ANY))

    def test_add_cname_record_without_valid_dnszone(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord with an invalid name
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='CNAME', value='bar.example.com').add().commit()
        self.assertEqual(cm.exception.args, ('name', mock.ANY))

    def test_add_txt_record(self):
        # Given an empty database
        DnsZone(name='example.com').add().commit()
        # When adding a DnsRecord
        DnsRecord(name='foo.example.com', type='TXT', value='some data').add().commit()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    def test_add_txt_record_with_invalid_value(self):
        # Given an empty database
        DnsZone(name='examples.com').add().commit()
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='TXT', value='').add().commit()
        self.assertEqual(cm.exception.args, ('value', mock.ANY))

    def test_add_txt_record_without_valid_dnszone(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord
        # Then an error is raise
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='TXT', value='some data').add().commit()
        self.assertEqual(cm.exception.args, ('name', mock.ANY))

    def test_add_ipv4_ptr_record(self):
        # Given a valid DNS Zone
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['192.0.2.0/24'], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        # When adding a DnsRecord
        DnsRecord(name='254.2.0.192.in-addr.arpa', type='PTR', value='bar.example.com').add().commit()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())
        # Then revice_ip is valid
        record = DnsRecord.query.first()
        self.assertEqual('192.0.2.254', record.ip_value)

    def test_add_ipv4_ptr_record_without_valid_dnszone(self):
        # Given a valid DNS Zone
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['192.0.5.0/24'], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        # When adding a DnsRecord with invalid DNS Zone
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='255.2.0.192.in-addr.arpa', type='PTR', value='bar.example.com').add().commit()
        self.assertEqual(cm.exception.args, ('name', 'IP address must be defined within the DNS Zone: 192.0.5.0/24'))

    def test_add_ipv6_ptr_record(self):
        # Given a valid DNS Zone
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['4321:0:1:2:3:4:567:0/112'], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        # When adding a DnsRecord
        DnsRecord(
            name='b.a.9.8.7.6.5.0.4.0.0.0.3.0.0.0.2.0.0.0.1.0.0.0.0.0.0.0.1.2.3.4.ip6.arpa',
            type='PTR',
            value='bar.example.com',
        ).add().commit()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    def test_add_ipv6_ptr_record_without_valid_dnszone(self):
        # Given a valid DNS Zone
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['4321:0:1:2:3:4:567:0/128'], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        # When adding a DnsRecord
        with self.assertRaises(ValueError) as cm:
            DnsRecord(
                name='b.a.9.8.7.6.5.0.4.0.0.0.3.0.0.0.2.0.0.0.1.0.0.0.0.0.0.0.1.2.3.4.ip6.arpa',
                type='PTR',
                value='bar.example.com',
            ).add().commit()
        self.assertEqual(
            cm.exception.args, ('name', 'IP address must be defined within the DNS Zone: 4321:0:1:2:3:4:567:0/128')
        )

    def test_add_ipv6_ptr_uppercase(self):
        # Given a valid DNS Zone
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['4321:0:1:2:3:4:567:0/112'], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        # Given an ipv6 record in uppercase
        name = 'b.a.9.8.7.6.5.0.4.0.0.0.3.0.0.0.2.0.0.0.1.0.0.0.0.0.0.0.1.2.3.4.IP6.ARPA'
        # When adding the record to the database
        DnsRecord(name=name, type='PTR', value='bar.example.com').add().commit()
        # Then the record is added with lowercase
        self.assertEqual(name.lower(), DnsRecord.query.first().name)

    def test_add_ptr_record_with_invalid_value(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='PTR', value='192.0.2.23').add().commit()
        self.assertEqual(cm.exception.args, ('value', mock.ANY))

    def test_add_ptr_record_with_invalid_name(self):
        # Given an empty database
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['4321:0:1:2:3:4:567:0/112'], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='PTR', value='foo.example.com').add().commit()
        self.assertEqual(cm.exception.args, ('name', mock.ANY))

    def test_add_ns_record(self):
        # Given an empty database
        DnsZone(name='example.com').add().commit()
        # When adding a DnsRecord
        DnsRecord(name='foo.example.com', type='NS', value='bar.example.com').add().commit()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    def test_add_ns_record_with_invalid_value(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='NS', value='192.0.2.23').add().commit()
        self.assertEqual(cm.exception.args, ('value', mock.ANY))

    def test_get_reverse_dns_record_with_ipv4(self):
        # Given a A DNS Record
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['192.0.2.0/24'], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        a_record = DnsRecord(name='foo.example.com', value='192.0.2.1', type='A').add()
        # Given a PTR DNS Record
        prt_record = DnsRecord(name='1.2.0.192.in-addr.arpa', value='foo.example.com', type='PTR').add().commit()
        # When getting reverse record
        # Then the PTR Record is return
        self.assertEqual(a_record, prt_record.get_reverse_dns_record())
        self.assertEqual(prt_record, a_record.get_reverse_dns_record())

    def test_get_reverse_dns_record_with_ipv6(self):
        # Given a A DNS Record
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['2a07:6b43:26:11::/64'], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        a_record = DnsRecord(name='foo.example.com', value='2a07:6b43:26:11::1', type='AAAA').add()
        # Given a PTR DNS Record
        prt_record = DnsRecord(
            name='1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.1.0.0.6.2.0.0.3.4.b.6.7.0.a.2.ip6.arpa',
            value='foo.example.com',
            type='PTR',
        )
        prt_record.add().commit()
        # When getting reverse record
        # Then the PTR Record is return
        self.assertEqual(a_record, prt_record.get_reverse_dns_record())
        self.assertEqual(prt_record, a_record.get_reverse_dns_record())

    @parameterized.expand(
        [
            ('_acme-challenge.example.com', 'example.com._acme.example.info', 'CNAME'),
            ('jlco-tpm1.bfh.ch_.example.com', 'example.info', 'CNAME'),
        ]
    )
    def test_add_cname_with_underscore(self, name, value, type):
        # Given a database with a zone
        DnsZone(name='example.com').add()
        DnsZone(name='example.info').add().flush()
        # When adding a CNAME with underscore
        DnsRecord(name=name, value=value, type=type).add().flush()
        # Then record get added
        DnsRecord.query.one()
