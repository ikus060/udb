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
from udb.core.model import DhcpRecord, DnsRecord, DnsZone, Ip, Subnet, Vrf


class IpTest(WebCase):
    def test_duplicate_with_dhcp_records(self):
        # Given a empty database
        # When creating multiple DHCP Record with the same IP
        dhcp_record1 = DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:bf').add()
        dhcp_record2 = DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:bc').add().commit()
        # Then a single IP Record is created
        self.assertEqual(1, Ip.query.count())
        ip_record = Ip.query.first()
        self.assertIn(dhcp_record1, ip_record.related_dhcp_records)
        self.assertIn(dhcp_record2, ip_record.related_dhcp_records)
        # And history is tracking changes
        self.assertTrue(ip_record.messages)
        self.assertIn('related_dhcp_records', ip_record.messages[0].changes)

    def test_duplicate_with_dns_records(self):
        # Given a Vrf, Subnet and DnsZone
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['192.0.2.0/24'], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        # When creating multiple Dns Record with the same IP
        dns_record1 = DnsRecord(name='foo.example.com', type='A', value='192.0.2.20').add()
        dns_record2 = DnsRecord(name='bar.example.com', type='A', value='192.0.2.20').add().commit()
        # Then a single IP Record is created
        self.assertEqual(1, Ip.query.count())
        ip_record = Ip.query.first()
        self.assertIn(dns_record1, ip_record.related_dns_records)
        self.assertIn(dns_record2, ip_record.related_dns_records)
        # And history is tracking changes
        self.assertTrue(ip_record.messages)
        self.assertIn('related_dns_records', ip_record.messages[0].changes)

    def test_ip(self):
        # Given valid DnsZone with subnet
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['192.0.2.0/24'], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        # Given a list of DhcpRecord and DnsRecord
        DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:bf').add()
        DhcpRecord(ip='192.0.2.24', mac='00:00:5e:00:53:df').add()
        DhcpRecord(ip='192.0.2.25', mac='00:00:5e:00:53:cf').add()
        DnsRecord(name='foo.example.com', type='A', value='192.0.2.20').add()
        DnsRecord(name='bar.example.com', type='A', value='192.0.2.23').add().commit()
        # When querying list of IPs
        objs = Ip.query.order_by('ip').all()
        # Then is matches the DhcpRecord.
        self.assertEqual(len(objs), 4)
        self.assertEqual(objs[0].ip, '192.0.2.20')
        self.assertEqual(objs[1].ip, '192.0.2.23')
        self.assertEqual(objs[2].ip, '192.0.2.24')
        self.assertEqual(objs[3].ip, '192.0.2.25')

    def test_ip_with_dhcp_deleted_status(self):
        # Given a deleted DhcpRecord
        DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:bf', status='deleted').add().commit()
        # When querying list of IPs
        objs = Ip.query.order_by('ip').all()
        # Then an Ip record got created
        self.assertEqual(len(objs), 1)

    def test_ip_with_dns_deleted_status(self):
        # Given valid DnsZone with subnet
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['192.0.2.0/24'], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().commit()
        # Given a deleted DnsRecord
        DnsRecord(name='foo.example.com', type='A', value='192.0.2.20', status='deleted').add().commit()
        # When querying list of IPs
        objs = Ip.query.order_by('ip').all()
        # Then the list is empty
        self.assertEqual(len(objs), 1)

    def test_ip_get_dns_records(self):
        # Given valid DnsZone with subnet
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['192.0.2.0/24'], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        # Given a list of DnsRecords and DhcpRecord
        DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:bf').add()
        DnsRecord(name='bar.example.com', type='A', value='192.0.2.23').add()
        DnsRecord(name='bar.example.com', type='TXT', value='x47').add().commit()
        # When querying list of related DnsRecord on a Ip.
        objs = Ip.query.order_by('ip').first().related_dns_records
        # Then the list include a single DnsRecord
        self.assertEqual(len(objs), 1)
        self.assertEqual(objs[0].name, 'bar.example.com')

    def test_ip_get_dhcp_records(self):
        # Given valid DnsZone with subnet
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['192.0.2.0/24'], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        # Given a list of DnsRecords and DhcpRecord
        DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:bf').add()
        DnsRecord(name='bar.example.com', type='A', value='192.0.2.23').add()
        DnsRecord(name='bar.example.com', type='TXT', value='x47').add().commit()
        # When querying list of related DhcpRecord on a Ip.
        objs = Ip.query.order_by('ip').first().related_dhcp_records
        # Then the list include all DhcpRecord matching the fqdn
        self.assertEqual(len(objs), 1)
        self.assertEqual(objs[0].mac, '00:00:5e:00:53:bf')

    def test_ipv6_related_records(self):
        # Given a DnsZone with valid subnet
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['2001:db8:85a3::/64'], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        # Given a list of DnsRecords and DhcpRecord with ipv6
        DhcpRecord(ip='2001:0db8:85a3:0000:0000:8a2e:0370:7334', mac='00:00:5e:00:53:bf').add().commit()
        DnsRecord(name='bar.example.com', type='AAAA', value='2001:0db8:85a3:0000:0000:8a2e:0370:7334').add().commit()
        # When querying list of related DnsRecord on a Ip.
        self.assertEqual(1, Ip.query.count())
        obj = Ip.query.order_by('ip').first()
        # Then the list include all DnsRecord matching the fqdn
        self.assertEqual(len(obj.related_dhcp_records), 1)
        self.assertEqual(len(obj.related_dns_records), 1)

    def test_dns_aaaa_ipv6(self):
        # Given a DnsZone with valid subnet
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['2001:db8:85a3::/64'], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        # Given a DnsRecords with ipv6
        DnsRecord(name='bar.example.com', type='AAAA', value='2001:0db8:85a3:0000:0000:8a2e:0370:7334').add().commit()
        # When querying list of related DnsRecord on a Ip.
        obj = Ip.query.order_by('ip').first()
        # Then the list include all DnsRecord matching the fqdn
        self.assertEqual(len(obj.related_dhcp_records), 0)
        self.assertEqual(len(obj.related_dns_records), 1)

    def test_dhcp_ipv6(self):
        # Given a DhcpRecord with ipv6
        DhcpRecord(ip='2001:0db8:85a3:0000:0000:8a2e:0370:7334', mac='00:00:5e:00:53:bf').add().commit()
        # When querying list of related DhcpRecord on a Ip.
        obj = Ip.query.order_by('ip').first()
        # Then the list include all DhcpRecord matching the fqdn
        self.assertEqual(len(obj.related_dhcp_records), 1)
        self.assertEqual(len(obj.related_dns_records), 0)

    def test_related_dns_record_with_ptr_ipv4(self):
        # Given a valid PTR record in DNS Zone
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['192.168.2.0/24'], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        DnsRecord(name='254.2.168.192.in-addr.arpa', type='PTR', value='bar.example.com').add().commit()
        # When querying list of IP
        obj = Ip.query.order_by('ip').first()
        # Then is include the IP Address of the PTR record
        self.assertEqual('192.168.2.254', obj.ip)
        self.assertEqual(len(obj.related_dns_records), 1)

    def test_related_dns_record_with_ptr_ipv6(self):
        # Given a valid PTR record in DNS Zone
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['4321:0:1:2:3:4:567:0/112'], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        DnsRecord(
            name='b.a.9.8.7.6.5.0.4.0.0.0.3.0.0.0.2.0.0.0.1.0.0.0.0.0.0.0.1.2.3.4.ip6.arpa',
            type='PTR',
            value='bar.example.com',
        ).add().commit()
        # When querying list of IP
        obj = Ip.query.order_by('ip').first()
        # Then is include the IP Address of the PTR record
        self.assertEqual('4321:0:1:2:3:4:567:89ab', obj.ip)
        self.assertEqual(len(obj.related_dns_records), 1)

    def test_related_dhcp_record_ipv6(self):
        # Given a DNS Record within a valid DNS Zone
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['2001:db8:85a3::8a2e:370:7330/124'], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        dns = (
            DnsRecord(
                name='4.3.3.7.0.7.3.0.e.2.a.8.0.0.0.0.0.0.0.0.3.a.5.8.8.b.d.0.1.0.0.2.ip6.arpa',
                type='PTR',
                value='bar.example.com',
            )
            .add()
            .commit()
        )
        # Given a deleted DHCP Reservation
        dhcp = (
            DhcpRecord(
                ip='2001:0db8:85a3:0000:0000:8a2e:0370:7334',
                mac='00:00:5e:00:53:bf',
            )
            .add()
            .commit()
        )
        # When querying list of IP
        self.assertEqual(1, Ip.query.count())
        obj = Ip.query.order_by('ip').first()
        # Then is include the IP Address of the PTR record
        self.assertEqual('2001:db8:85a3::8a2e:370:7334', obj.ip)
        self.assertEqual([dhcp], obj.related_dhcp_records)
        self.assertEqual([dns], obj.related_dns_records)

    def test_related_dns_record_with_deleted(self):
        # Given a DHCP Reservation
        DhcpRecord(
            ip='2001:0db8:85a3:0000:0000:8a2e:0370:7334',
            mac='00:00:5e:00:53:bf',
        ).add().commit()
        # Given a deleted DNS Record
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['2001:db8:85a3::8a2e:370:7334/126'], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        DnsRecord(
            name='4.3.3.7.0.7.3.0.e.2.a.8.0.0.0.0.0.0.0.0.3.a.5.8.8.b.d.0.1.0.0.2.ip6.arpa',
            type='PTR',
            value='bar.example.com',
            status=DnsRecord.STATUS_DELETED,
        ).add().commit()
        # When querying list of IP
        obj = Ip.query.order_by('ip').first()
        # Then value is include the IP Address of the PTR record
        self.assertEqual('2001:db8:85a3::8a2e:370:7334', obj.ip)
        self.assertEqual(len(obj.related_dns_records), 1)

    def test_related_dhcp_record_with_deleted(self):
        # Given a DNS Record in DNS Zone
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['2001:db8:85a3::8a2e:370:7334/126'], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        DnsRecord(
            name='4.3.3.7.0.7.3.0.e.2.a.8.0.0.0.0.0.0.0.0.3.a.5.8.8.b.d.0.1.0.0.2.ip6.arpa',
            type='PTR',
            value='bar.example.com',
        ).add().commit()
        # Given a deleted DHCP Reservation
        DhcpRecord(
            ip='2001:0db8:85a3:0000:0000:8a2e:0370:7334',
            mac='00:00:5e:00:53:bf',
            status=DhcpRecord.STATUS_DELETED,
        ).add().commit()
        # When querying list of IP
        obj = Ip.query.order_by('ip').first()
        # Then value is include the IP Address of the PTR record
        self.assertEqual('2001:db8:85a3::8a2e:370:7334', obj.ip)
        self.assertEqual(len(obj.related_dhcp_records), 1)

    def test_related_subnets(self):
        # Given a DNS Record in DNS Zone
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['2001:db8:85a3::8a2e:370:7334/126'], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        DnsRecord(
            name='4.3.3.7.0.7.3.0.e.2.a.8.0.0.0.0.0.0.0.0.3.a.5.8.8.b.d.0.1.0.0.2.ip6.arpa',
            type='PTR',
            value='bar.example.com',
        ).add().commit()
        # Given a deleted DHCP Reservation
        DhcpRecord(
            ip='2001:0db8:85a3:0000:0000:8a2e:0370:7334',
            mac='00:00:5e:00:53:bf',
        ).add().commit()
        # When querying the related subnets
        obj = Ip.query.order_by('ip').first()
        self.assertEqual([subnet], obj.related_subnets)

    def test_update_dhcp_record_ip(self):
        # Given a DhcpRecord
        record = DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:bf').add().commit()
        # When updating the IP value
        record.ip = '192.0.2.24'
        record.commit()
        # Then a new IP Record get created
        Ip.query.filter(Ip.ip == '192.0.2.23').one()
        Ip.query.filter(Ip.ip == '192.0.2.24').one()

    def test_update_dns_record_ip(self):
        # Given a DnsRecord
        # Given a DNS Record in DNS Zone
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['192.0.2.0/24'], vrf=vrf).add()
        DnsZone(name='example.com', subnets=[subnet]).add().flush()
        record = DnsRecord(
            name='bar.example.com',
            type='A',
            value='192.0.2.23',
        )
        record.add().commit()
        # When updating the IP value
        record.value = '192.0.2.24'
        record.commit()
        # Then a new IP Record get created
        Ip.query.filter(Ip.ip == '192.0.2.23').one()
        Ip.query.filter(Ip.ip == '192.0.2.24').one()
