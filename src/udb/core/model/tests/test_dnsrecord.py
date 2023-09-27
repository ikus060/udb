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
from sqlalchemy.exc import IntegrityError

from udb.controller.tests import WebCase
from udb.core.model import DnsRecord, DnsZone, Rule, RuleError, Subnet, SubnetRange, Vrf


class DnsRecordTest(WebCase):
    def test_json(self):
        # Given a DnsRecord
        vrf = Vrf(name='default')
        subnet = Subnet(subnet_ranges=[SubnetRange('192.0.2.0/24')], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        obj = DnsRecord(name='foo.example.com', type='A', value='192.0.2.23', vrf=vrf).add().commit()
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
    def test_generated_ip_and_hostname_value(self, data, expected_ip_value, expected_hostname_value):
        # Given a Vrf, Subnet and DnsZone
        vrf = Vrf(name='default')
        DnsZone(name='example.com').add().flush()
        all_zone = DnsZone.query.all()
        Subnet(
            subnet_ranges=[
                SubnetRange('192.168.1.0/24'),
                SubnetRange('2001:db8::/64'),
                SubnetRange('4321:0:1:2:3:4:567:0/112'),
            ],
            dnszones=all_zone,
            vrf=vrf,
        ).add().commit()
        # When creating a DnsRecord
        record = DnsRecord(vrf=vrf, **data).add().commit()
        # Then validate ip_value
        self.assertEqual(expected_ip_value, record.ip_value)
        self.assertEqual(expected_hostname_value, record.hostname_value)
        # When using ip to make a query a record is returned
        DnsRecord.query.filter(DnsRecord.generated_ip == expected_ip_value).one()
        # When using hostname_value to make a query a record is returned
        DnsRecord.query.filter(DnsRecord.hostname_value == expected_hostname_value).one()

    def test_add_without_type(self):
        DnsZone(name='example.com').add().flush()
        with self.assertRaises(IntegrityError) as cm:
            DnsRecord(name='foo.example.com', type='', value='192.0.2.23').add().commit()
        self.assertIn('dnsrecord_types_ck', str(cm.exception))

    def test_add_a_record(self):
        # Given a database with a subnet and a dnszone
        vrf = Vrf(name='default')
        subnet = Subnet(subnet_ranges=[SubnetRange('192.0.2.0/24')], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord
        DnsRecord(name='foo.example.com', type='A', value='192.0.2.23', vrf=vrf).add().commit()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    def test_add_a_record_with_invalid_value(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='A', value='invalid').add().commit()
        self.assertEqual(cm.exception.args[0], 'value')
        self.assertEqual(cm.exception.args[1], 'value must be a valid IPv4 address')

    @parameterized.expand(
        [
            (DnsRecord(name='foo.example.com', type='A', value='192.0.2.23', vrf_id=1),),
            (DnsRecord(name='foo.example.com', type='AAAA', value='2002::1234:abcd:ffff:c0a7:101', vrf_id=1),),
            (DnsRecord(name='foo.example.com', type='CNAME', value='bar.example.com'),),
            (DnsRecord(name='foo.example.com', type='TXT', value='some data'),),
        ]
    )
    def test_add_record_without_valid_dnszone(self, record):
        # Given an empty database with a single VRF
        Vrf(name='default').add().commit()
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord
        # Then an exception is raised
        with self.assertRaises(IntegrityError) as cm:
            record = record.add().commit()
        self.assertIn('dnsrecord_dnszone_required_ck', str(cm.exception))

    def test_add_a_record_without_valid_subnet(self):
        # Given a database with a Subnet and a DnsZone
        vrf = Vrf(name='default')
        subnet = Subnet(subnet_ranges=[SubnetRange('10.255.0.0/16')], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        # When adding a DnsRecord
        # Then an exception is raised
        with self.assertRaises(IntegrityError) as cm:
            DnsRecord(name='foo.example.com', type='A', value='192.0.2.23', vrf=vrf).add().commit()
        self.assertIn('dnsrecord_subnetrange_required_ck', str(cm.exception))

    def test_add_a_record_with_host_subnet(self):
        # Given a database with a Subnet and a DnsZone
        vrf = Vrf(name='default')
        subnet = Subnet(subnet_ranges=[SubnetRange('192.0.2.23/32')], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        # When adding a DnsRecord
        DnsRecord(name='foo.example.com', type='A', value='192.0.2.23', vrf=vrf).add().commit()
        # Then not exception are raised

    def test_add_aaaa_record(self):
        # Given an empty database
        vrf = Vrf(name='default')
        subnet = Subnet(subnet_ranges=[SubnetRange('2002:0:0:1234::/64')], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        # When adding a DnsRecord
        DnsRecord(name='foo.example.com', type='AAAA', value='2002::1234:abcd:ffff:c0a9:101', vrf=vrf).add().commit()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    def test_add_aaaa_record_with_invalid_value(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='AAAA', value='invalid').add().commit()
        self.assertEqual('value', str(cm.exception.args[0]))
        self.assertEqual('value must be a valid IPv6 address', str(cm.exception.args[1]))

    def test_add_aaaa_record_without_valid_subnet(self):
        # Given a database with a valid DNSZone
        vrf = Vrf(name='default')
        subnet = Subnet(subnet_ranges=[SubnetRange('10.0.0.0/8')], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        # When adding a DnsRecord
        # Then an error is raised
        with self.assertRaises(IntegrityError) as cm:
            DnsRecord(
                name='foo.example.com', type='AAAA', value='2002::1234:abcd:ffff:c0a6:101', vrf=vrf
            ).add().commit()
        self.assertIn('dnsrecord_subnetrange_required_ck', str(cm.exception))

    def test_add_cname_record(self):
        # Given a DnsZone
        DnsZone(name='example.com').add().flush()
        # When adding a DnsRecord
        DnsRecord(name='foo.example.com', type='CNAME', value='bar.example.com').add().commit()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    def test_add_txt_record(self):
        # Given an empty database
        DnsZone(name='example.com').add().commit()
        # When adding a DnsRecord
        DnsRecord(name='foo.example.com', type='TXT', value='some data').add().commit()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    def test_add_txt_record_with_invalid_value(self):
        # Given an empty database
        DnsZone(name='example.com').add().commit()
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(IntegrityError) as cm:
            DnsRecord(name='foo.example.com', type='TXT', value='').add().commit()
        self.assertIn('dnsrecord_value_not_empty', str(cm.exception.args))

    def test_add_ipv4_ptr_record(self):
        # Given a valid DNS Zone
        vrf = Vrf(name='default')
        zone = DnsZone.query.filter(DnsZone.name == 'in-addr.arpa').first()
        Subnet(subnet_ranges=[SubnetRange('192.0.2.0/24')], dnszones=[zone], vrf=vrf).add().commit()
        # When adding a DnsRecord
        DnsRecord(name='254.2.0.192.in-addr.arpa', type='PTR', value='bar.example.com', vrf=vrf).add().commit()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())
        # Then revice_ip is valid
        record = DnsRecord.query.first()
        self.assertEqual('192.0.2.254', record.ip_value)

    def test_add_ipv4_ptr_record_without_valid_dnszone(self):
        # Given a valid DNS Zone
        vrf = Vrf(name='default')
        zone = DnsZone.query.filter(DnsZone.name == 'in-addr.arpa').first()
        Subnet(subnet_ranges=[SubnetRange('192.0.5.0/24')], dnszones=[zone], vrf=vrf).add().commit()
        # When adding a DnsRecord with invalid DNS Zone
        # Then an error is raised
        with self.assertRaises(IntegrityError) as cm:
            DnsRecord(name='255.2.0.192.in-addr.arpa', type='PTR', value='bar.example.com', vrf=vrf).add().commit()
        self.assertIn('dnsrecord_subnetrange_required_ck', str(cm.exception))

    def test_add_ipv6_ptr_record(self):
        # Given a valid DNS Zone
        vrf = Vrf(name='default')
        zone = DnsZone.query.filter(DnsZone.name == 'ip6.arpa').first()
        Subnet(subnet_ranges=[SubnetRange('4321:0:1:2:3:4:567:0/112')], dnszones=[zone], vrf=vrf).add().commit()
        # When adding a DnsRecord
        DnsRecord(
            name='b.a.9.8.7.6.5.0.4.0.0.0.3.0.0.0.2.0.0.0.1.0.0.0.0.0.0.0.1.2.3.4.ip6.arpa',
            type='PTR',
            value='bar.example.com',
            vrf=vrf,
        ).add().commit()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    def test_add_ipv6_ptr_record_without_valid_dnszone(self):
        # Given a valid DNS Zone
        vrf = Vrf(name='default')
        zone = DnsZone.query.filter(DnsZone.name == 'ip6.arpa').first()
        Subnet(subnet_ranges=[SubnetRange('4321:0:1:2:3:4:567:0/128')], dnszones=[zone], vrf=vrf).add().commit()
        # When adding a DnsRecord
        # Then error is raised
        with self.assertRaises(IntegrityError) as cm:
            DnsRecord(
                name='b.a.9.8.7.6.5.0.4.0.0.0.3.0.0.0.2.0.0.0.1.0.0.0.0.0.0.0.1.2.3.4.ip6.arpa',
                type='PTR',
                value='bar.example.com',
                vrf=vrf,
            ).add().commit()
        self.assertIn('dnsrecord_subnetrange_required_ck', str(cm.exception))

    def test_add_ipv6_ptr_uppercase(self):
        # Given a valid DNS Zone
        vrf = Vrf(name='default')
        zone = DnsZone.query.filter(DnsZone.name == 'ip6.arpa').first()
        Subnet(subnet_ranges=[SubnetRange('4321:0:1:2:3:4:567:0/112')], dnszones=[zone], vrf=vrf).add().commit()
        # Given an ipv6 record in uppercase
        name = 'b.a.9.8.7.6.5.0.4.0.0.0.3.0.0.0.2.0.0.0.1.0.0.0.0.0.0.0.1.2.3.4.IP6.ARPA'
        # When adding the record to the database
        DnsRecord(name=name, type='PTR', value='bar.example.com', vrf=vrf).add().commit()
        # Then the record is added with lowercase
        self.assertEqual(name.lower(), DnsRecord.query.first().name)

    def test_add_ptr_record_with_invalid_value(self):
        # Given a valid DNS Zone
        vrf = Vrf(name='default')
        zone = DnsZone.query.filter(DnsZone.name == 'ip6.arpa').first()
        Subnet(subnet_ranges=[SubnetRange('4321:0:1:2:3:4:567:0/112')], dnszones=[zone], vrf=vrf).add().commit()
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(IntegrityError) as cm:
            DnsRecord(
                name='b.a.9.8.7.6.5.0.4.0.0.0.3.0.0.0.2.0.0.0.1.0.0.0.0.0.0.0.1.2.3.4.ip6.arpa',
                type='PTR',
                value='192.0.2.23',
                vrf=vrf,
            ).add().commit()
        self.assertIn('dnsrecord_value_domain_name', str(cm.exception))

    def test_add_ptr_record_with_invalid_name(self):
        # Given an empty database
        vrf = Vrf(name='default')
        subnet = Subnet(subnet_ranges=[SubnetRange('4321:0:1:2:3:4:567:0/112')], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='PTR', value='foo.example.com', vrf=vrf).add().commit()
        self.assertEqual('name', str(cm.exception.args[0]))
        self.assertEqual(
            'PTR records must ends with `.in-addr.arpa` or `.ip6.arpa` and define a valid IPv4 or IPv6 address',
            str(cm.exception.args[1]),
        )

    def test_add_ns_record(self):
        # Given an empty database
        DnsZone(name='example.com').add().commit()
        # When adding a DnsRecord
        DnsRecord(name='foo.example.com', type='NS', value='bar.example.com').add().commit()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    @parameterized.expand(['CNAME', 'NS'])
    def test_add_record_with_invalid_domain_value(self, record_type):
        # Given a database with a DNS Zone
        vrf = Vrf(name='default')
        subnet = Subnet(subnet_ranges=[SubnetRange('192.0.2.0/24')], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised by database
        with self.assertRaises(IntegrityError) as cm:
            DnsRecord(name='foo.example.com', type=record_type, value='192.0.2.23').add().commit()
        self.assertIn('dnsrecord_value_domain_name', str(cm.exception))

    def test_get_reverse_dns_record_with_ipv4(self):
        # Given a A DNS Record
        vrf = Vrf(name='default').add()
        zone = DnsZone.query.filter(DnsZone.name == 'in-addr.arpa').first()
        subnet = Subnet(subnet_ranges=[SubnetRange('192.0.2.0/24')], dnszones=[zone], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        a_record = DnsRecord(name='foo.example.com', value='192.0.2.1', type='A', vrf=vrf).add().commit()
        # Given a PTR DNS Record
        prt_record = (
            DnsRecord(name='1.2.0.192.in-addr.arpa', value='foo.example.com', type='PTR', vrf=vrf).add().commit()
        )
        # When getting reverse record
        # Then the PTR Record is return
        self.assertEqual(a_record, prt_record.get_reverse_dns_record())
        self.assertEqual(prt_record, a_record.get_reverse_dns_record())

    def test_get_reverse_dns_record_with_ipv6(self):
        # Given a A DNS Record
        vrf = Vrf(name='default')
        zone = DnsZone.query.filter(DnsZone.name == 'ip6.arpa').first()
        subnet = Subnet(subnet_ranges=[SubnetRange('2a07:6b43:26:11::/64')], dnszones=[zone], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        a_record = DnsRecord(name='foo.example.com', value='2a07:6b43:26:11::1', type='AAAA', vrf=vrf).add().commit()
        # Given a PTR DNS Record
        prt_record = DnsRecord(
            name='1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.1.1.0.0.6.2.0.0.3.4.b.6.7.0.a.2.ip6.arpa',
            value='foo.example.com',
            type='PTR',
            vrf=vrf,
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

    def test_add_multiple_soa(self):
        # Given an existing SOA record on the DNS Zone
        DnsZone(name='example.com').add().flush()
        DnsRecord(
            name='example.com',
            value='ddns.bfh.info. bfh-linux-sysadmin.lists.bfh.science. 33317735 600 60 36000 3600',
            type='SOA',
        ).add().commit()
        # When trying to create a second SOA record for the same hostname
        # Then an error is raised
        with self.assertRaises(IntegrityError):
            DnsRecord(
                name='example.com',
                value='ddns.bfh.info. bfh-linux-sysadmin.lists.bfh.science. 33317735 600 60 36000 3600',
                type='SOA',
            ).add().commit()

    def test_add_soa_without_dnszone(self):
        # Given a DnsZone
        DnsZone(name='example.com').add().commit()
        # When creating a SOA on sub-domain
        # Then an error is raised
        with self.assertRaises(IntegrityError) as cm:
            DnsRecord(
                name='foo.example.com',
                value='ddns.bfh.info. bfh-linux-sysadmin.lists.bfh.science. 33317735 600 60 36000 3600',
                type='SOA',
            ).add().commit()
        self.assertIn('dnsrecord_soa_dnszone_ck', str(cm.exception))

    def test_invalid_record_type(self):
        # Given a DnsZone
        DnsZone(name='example.com').add().commit()
        # When flushing the object
        # Then an error is raised.
        with self.assertRaises(IntegrityError) as cm:
            DnsRecord(name='bar.example.com', type='INVA', value='testing').add().flush()
        self.assertIn('dnsrecord_types_ck', str(cm.exception))

    def test_dnsrecord_cname_unique_rule(self):
        # Given a CNAME and a A record on the same host
        DnsZone(name='example.com').add().flush()
        DnsRecord(name='www.example.com', type='CNAME', value='example.com').add().commit()
        # When creating another record
        other = DnsRecord(name='www.example.com', type='TXT', value='value').add().commit()
        # Then an error is raised
        # Then an exception is raised by Soft Rule
        with self.assertRaises(RuleError) as cm:
            Rule.verify(other, errors='raise')
        self.assertIn('dnsrecord_cname_unique_rule', str(cm.exception))

    def test_null_vrf(self):
        # Given a dns record
        vrf = Vrf(name='default')
        subnet = Subnet(subnet_ranges=[SubnetRange('192.0.2.0/24')], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        self.assertEqual(0, DnsRecord.query.count())
        record = DnsRecord(name='foo.example.com', type='A', value='192.0.2.23', vrf=vrf).add().commit()
        # When updating the vrf to null
        record.vrf = None
        record.add().commit()
        # Then a new default VRF get assigned
        self.assertEqual(record.vrf, vrf)

    def test_parent_dnszone(self):
        # Given a database with a DNS Record
        vrf = Vrf(name='default')
        subnet = Subnet(subnet_ranges=[SubnetRange('192.0.2.0/24')], vrf=vrf)
        zone = DnsZone(name='example.com', subnets=[subnet]).add().commit()
        self.assertEqual(0, DnsRecord.query.count())
        record = DnsRecord(name='foo.example.com', type='A', value='192.0.2.23', vrf=vrf).add().commit()
        # When getting the parent_dnszone of the record.
        # Then we get reference to the right one.
        self.assertEqual(zone, record._dnszone)

    def test_parent_dnszone_with_subzone(self):
        # Given a database with a DNS Record
        vrf = Vrf(name='default')
        subnet = Subnet(subnet_ranges=[SubnetRange('192.0.2.0/24')], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        subzone = DnsZone(name='mmi.example.com', subnets=[subnet]).add().commit()
        self.assertEqual(0, DnsRecord.query.count())
        record = DnsRecord(name='foo.mmi.example.com', type='A', value='192.0.2.23', vrf=vrf).add().commit()
        # When getting the parent_dnszone of the record.
        # Then we get reference to the right one.
        self.assertEqual(subzone, record._dnszone)

    def test_estatus_with_vrf_status(self):
        # Given an enabled VRF and enabled DHCP
        vrf = Vrf(name='default')
        subnet = Subnet(subnet_ranges=[SubnetRange('192.0.2.0/24')], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        record = DnsRecord(name='foo.example.com', type='A', value='192.0.2.23', vrf=vrf).add().commit()
        # When deleting parent VRF.
        vrf.status = Vrf.STATUS_DELETED
        vrf.add().commit()
        # Then DHCP effective status is deleted.
        record.expire()
        self.assertEqual(DnsRecord.STATUS_DELETED, record.estatus)

    def test_estatus_with_subnet_status(self):
        # Given an enabled VRF and enabled DHCP
        vrf = Vrf(name='default')
        subnet = Subnet(subnet_ranges=[SubnetRange('192.0.2.0/24')], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        record = DnsRecord(name='foo.example.com', type='A', value='192.0.2.23', vrf=vrf).add().commit()
        # When deleting parent VRF.
        subnet.status = Vrf.STATUS_DELETED
        subnet.add().commit()
        # Then DHCP effective status is deleted.
        record.expire()
        self.assertEqual(DnsRecord.STATUS_DELETED, record.estatus)

    def test_estatus_with_zone_status(self):
        # Given an enabled VRF and enabled DHCP
        vrf = Vrf(name='default')
        subnet = Subnet(subnet_ranges=[SubnetRange('192.0.2.0/24')], vrf=vrf)
        zone = DnsZone(name='example.com', subnets=[subnet]).add().commit()
        record = DnsRecord(name='foo.example.com', type='CNAME', value='example.com').add().commit()
        # When deleting parent VRF.
        zone.status = Vrf.STATUS_DELETED
        zone.add().commit()
        # Then DHCP effective status is deleted.
        record.expire()
        self.assertEqual(DnsRecord.STATUS_DELETED, record.estatus)

    def test_update_parent_dnszone_name(self):
        # Given a database with a DNS Zone and a DnsRecord
        vrf = Vrf(name='default')
        subnet = Subnet(subnet_ranges=[SubnetRange('192.0.2.0/24')], vrf=vrf)
        zone = DnsZone(name='example.com', subnets=[subnet]).add().commit()
        DnsRecord(name='foo.example.com', type='CNAME', value='example.com').add().commit()
        # When updating the DnsZone's name
        # Then an exception is raised.
        with self.assertRaises(IntegrityError) as cm:
            zone.name = 'test.com'
            zone.add().commit()
        self.assertIn('dnsrecord_dnszone_required_ck', str(cm.exception))

    def test_update_parent_subnet_range(self):
        # Given a database with a Subnet and a DnsRecord
        vrf = Vrf(name='default')
        subnet = Subnet(subnet_ranges=[SubnetRange('192.0.2.0/24')], vrf=vrf)
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        DnsRecord(name='foo.example.com', type='A', value='192.0.2.25').add().commit()
        # When updating the Subnet range.
        # Then an exception is raised.
        with self.assertRaises(IntegrityError) as cm:
            subnet.subnet_ranges[0].range = '192.0.10.0/24'
            subnet.commit()
        self.assertIn('dnsrecord_subnetrange_required_ck', str(cm.exception))
