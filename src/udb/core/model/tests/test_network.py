# -*- coding: utf-8 -*-
# udb, A web interface to manage IT network
# Copyright (C) 2021 IKUS Software inc.
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

from sqlalchemy.exc import IntegrityError

from udb.controller.tests import WebCase
from udb.core.model import DhcpRecord, DnsRecord, DnsZone, Ip, Message, Subnet, User


class DnsZoneTest(WebCase):
    def test_json(self):
        # Given a DnsZone
        obj = DnsZone(name='bfh.ch').add()
        # When serializing the object to json
        data = obj.to_json()
        # Then a json representation is return
        self.assertEqual(data['name'], 'bfh.ch')

    def test_add(self):
        # Given an empty database
        self.assertEqual(0, DnsZone.query.count())
        # When adding a new Dns Zone
        DnsZone(name='bfh.ch').add()
        # then a new DnsZone entry exists in database
        self.assertEqual(1, DnsZone.query.count())

    def test_delete(self):
        # Given a database with a DnsZone
        self.assertEqual(0, DnsZone.query.count())
        obj = DnsZone(name='bfh.ch').add()
        self.assertEqual(1, DnsZone.query.count())
        self.session.commit()
        # When trying to delete a given dns zone
        obj.delete()
        # When the entry is removed from database
        self.assertEqual(0, DnsZone.query.count())

    def test_soft_delete(self):
        # Given a datavase with a DnsZone
        obj = DnsZone(name='bfh.ch').add()
        self.assertEqual(1, DnsZone.query.count())
        # When updating it's status to deleted
        obj.status = DnsZone.STATUS_DELETED
        obj.add()
        # When the object still exists in database
        self.assertEqual(1, DnsZone.query.count())
        self.assertEqual(DnsZone.STATUS_DELETED, DnsZone.query.first().status)

    def test_enabled(self):
        # Given a datavase with a DnsZone
        obj = DnsZone(name='bfh.ch').add()
        self.assertEqual(1, DnsZone.query.count())
        # When updating it's status to deleted
        obj.status = DnsZone.STATUS_ENABLED
        obj.add()
        # Then the object still exists in database
        self.assertEqual(1, DnsZone.query.count())
        self.assertEqual(DnsZone.STATUS_ENABLED, DnsZone.query.first().status)

    def test_disabled(self):
        # Given a datavase with a DnsZone
        obj = DnsZone(name='bfh.ch').add()
        self.assertEqual(1, DnsZone.query.count())
        # When updating it's status to deleted
        obj.status = DnsZone.STATUS_DISABLED
        obj.add()
        # When the object still exists in database
        self.assertEqual(1, DnsZone.query.count())
        self.assertEqual(DnsZone.STATUS_DISABLED, DnsZone.query.first().status)

    def test_invalid_name(self):
        # Given an ampty database
        self.assertEqual(0, DnsZone.query.count())
        # When trying to create a new DnsZone with an invalid fqdn
        # Then an excpetion is raised
        with self.assertRaises(ValueError) as cm:
            DnsZone(name='invalid/name').add()
        self.assertEqual(cm.exception.args, ('name', mock.ANY))

    def test_duplicate_name(self):
        # Given a database with an existing record
        DnsZone(name='bfh.ch').add()
        self.assertEqual(1, DnsZone.query.count())
        self.session.commit()
        # When trying to add a dns zone with an existing name
        # Then an exception is raised
        with self.assertRaises(IntegrityError):
            DnsZone(name='bfh.ch').add()
            self.session.commit()

    def test_duplicate_name_case_insensitive(self):
        # Given a database with an existing record
        DnsZone(name='bfh.ch').add()
        self.assertEqual(1, DnsZone.query.count())
        self.session.commit()
        # When trying to add a dns zone with an existing name
        # Then an exception is raised
        with self.assertRaises(IntegrityError):
            DnsZone(name='BFH.ch').add()
            self.session.commit()

    def test_update_owner(self):
        # Given a database with an existing record
        d = DnsZone(name='bfh.ch').add()
        self.assertEqual(1, DnsZone.query.count())
        self.session.commit()
        # When trying to update the owner
        new_user = User(username='test').add()
        d.owner = new_user
        d.add()
        self.session.commit()
        # Then a new message with changes is append to the object.
        messages = d.get_messages()
        self.assertEqual(2, len(messages))
        self.assertEqual({'owner': [None, 'test']}, messages[-1].changes)

    def test_add_subnet(self):
        # Given a database with an existing record
        zone = DnsZone(name='bfh.ch').add()
        self.session.commit()
        # When trying to add an allowed subnet to the dns zone
        subnet = Subnet(name='test', ip_cidr='192.168.1.0/24', vrf=3).add()
        zone.subnets.append(subnet)
        zone.add()
        # Then a subnet is added
        zone = DnsZone.query.first()
        subnet = Subnet.query.first()
        self.assertEqual(1, len(zone.subnets))
        self.assertEqual('test', zone.subnets[0].name)
        self.assertEqual(1, len(zone.subnets[0].dnszones))
        self.assertEqual(zone, zone.subnets[0].dnszones[0])
        # Then an audit message is created for both objects
        self.assertEqual(2, len(zone.get_messages()))
        self.assertEqual(zone.get_messages()[-1].changes, {'subnets': [[], ['192.168.1.0/24 (test)']]})
        self.assertEqual(2, len(subnet.get_messages()))
        self.assertEqual(subnet.get_messages()[-1].changes, {'dnszones': [[], ['bfh.ch']]})

    def test_get_messages(self):
        # Given a database with an existing record
        d = DnsZone(name='bfh.ch').add()
        self.assertEqual(1, DnsZone.query.count())
        self.session.commit()
        # When updating the owner
        new_user = User(username='test').add()
        d.owner = new_user
        d.add()
        self.session.commit()
        # When adding a comments
        d.add_message(Message(body='this is a comments'))
        # Then a message with type 'new' exists
        messages = d.get_messages('new')
        self.assertEqual(1, len(messages))
        self.assertEqual(messages[0].changes, {'name': [None, 'bfh.ch']})
        # Then a message with type 'dirty' exists
        messages = d.get_messages('dirty')
        self.assertEqual(1, len(messages))
        self.assertEqual(messages[0].changes, {'owner': [None, 'test']})
        # Then a message with type 'comment' exists
        messages = d.get_messages('comment')
        self.assertEqual(1, len(messages))
        self.assertEqual(messages[0].changes, None)
        self.assertEqual(messages[0].body, 'this is a comments')
        # Then the list of message contains all tre message
        messages = d.get_messages()
        self.assertEqual(3, len(messages))


class SubnetTest(WebCase):
    def test_json(self):
        # Given a DnsZone
        obj = Subnet(name='test', ip_cidr='192.168.1.0/24', vrf=3).add()
        # When serializing the object to json
        data = obj.to_json()
        # Then a json representation is return
        self.assertEqual(
            data,
            {
                'created_at': mock.ANY,
                'id': 1,
                'ip_cidr': '192.168.1.0/24',
                'modified_at': mock.ANY,
                'name': 'test',
                'notes': '',
                'owner_id': None,
                'status': 'enabled',
                'vrf': 3,
            },
        )

    def test_add_ipv4(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with IPV4
        Subnet(ip_cidr='192.168.1.0/24').add()
        # Then a new record is created
        subnet = Subnet.query.first()
        self.assertEqual('192.168.1.0/24', subnet.ip_cidr)

    def test_add_ipv6(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with IPV6
        Subnet(ip_cidr='2002::1234:abcd:ffff:c0a8:101/64').add()
        # Then a new record is created
        subnet = Subnet.query.first()
        self.assertEqual('2002:0:0:1234::/64', subnet.ip_cidr)

    def test_invalid_ipv4(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with an invalid IP
        with self.assertRaises(ValueError) as cm:
            Subnet(ip_cidr='a.168.1.0/24').add()
        self.assertEqual(cm.exception.args, ('ip_cidr', mock.ANY))
        # Then a record is not created
        self.assertEqual(0, Subnet.query.count())

    def test_missing_ipv4(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet without an IP
        with self.assertRaises(IntegrityError):
            Subnet(name='foo').add()
        self.session.rollback()
        # Then a record is not created
        self.assertEqual(0, Subnet.query.count())

    def test_add_with_vrf(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with a VRF
        Subnet(ip_cidr='192.168.1.0/24', vrf=12).add()
        # Then a new record is created
        self.assertEqual(1, Subnet.query.count())

    def test_add_with_name(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with a name
        Subnet(ip_cidr='192.168.1.0/24', name='foo').add()
        # Then a new record is created
        self.assertEqual(1, Subnet.query.count())

    def test_duplicate_ip_cidr(self):
        # Given a database with an existing record
        Subnet(ip_cidr='192.168.1.0/24', name='foo').add()
        self.assertEqual(1, Subnet.query.count())
        # When trying to add a Subnet with an existing ip_CIDR
        # Then an exception is raised
        with self.assertRaises(IntegrityError):
            Subnet(ip_cidr='192.168.1.0/24', name='bar').add()

    def test_add_dnszonesubnet(self):
        # Given a database with an existing record
        subnet = Subnet(ip_cidr='192.168.1.0/24', name='foo').add()
        self.session.commit()
        # When trying to add an allowed subnet to the dns zone
        zone = DnsZone(name='bfh.ch').add()
        subnet.dnszones.append(zone)
        zone.add()
        # Then a subnet is added
        subnet = Subnet.query.first()
        zone = DnsZone.query.first()
        self.assertEqual(1, len(subnet.dnszones))
        self.assertEqual('bfh.ch', subnet.dnszones[0].name)
        self.assertEqual(1, len(subnet.dnszones[0].subnets))
        self.assertEqual(subnet, subnet.dnszones[0].subnets[0])
        # Then an audit message is created for both objects
        self.assertEqual(2, len(subnet.get_messages()))
        self.assertEqual(subnet.get_messages()[-1].changes, {'dnszones': [[], ['bfh.ch']]})
        self.assertEqual(2, len(zone.get_messages()))
        self.assertEqual(zone.get_messages()[-1].changes, {'subnets': [[], ['192.168.1.0/24 (foo)']]})

    def test_subnets(self):
        # Given a database with an existing record
        subnet1 = Subnet(ip_cidr='192.168.1.0/24', name='foo').add()
        subnet2 = Subnet(ip_cidr='192.168.1.128/30', name='bar').add()
        # When querying list of subnets
        subnets = subnet1.related_subnets
        # Then the list contains our subnet
        self.assertEqual([subnet2], subnets)

    def test_supernets(self):
        # Given a database with an existing record
        subnet1 = Subnet(ip_cidr='192.168.1.0/24', name='foo').add()
        subnet2 = Subnet(ip_cidr='192.168.1.128/30', name='bar').add()
        # When querying list of subnets
        subnets = subnet2.related_supernets
        # Then the list contains our subnet
        self.assertEqual([subnet1], subnets)


class DnsRecordTest(WebCase):
    def test_json(self):
        # Given a DnsRecord
        subnet = Subnet(ip_cidr='192.0.2.0/24')
        DnsZone(name='example.com', subnets=[subnet]).add()
        obj = DnsRecord(name='foo.example.com', type='A', value='192.0.2.23').add()
        # When serializing the object to json
        data = obj.to_json()
        # Then a json representation is return
        self.assertEqual(data['name'], 'foo.example.com')
        self.assertEqual(data['type'], 'A')
        self.assertEqual(data['ttl'], 3600)
        self.assertEqual(data['value'], '192.0.2.23')

    def test_add_a_record(self):
        # Given a database with a subnet and a dnszone
        subnet = Subnet(ip_cidr='192.0.2.0/24')
        DnsZone(name='example.com', subnets=[subnet]).add()
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord
        DnsRecord(name='foo.example.com', type='A', value='192.0.2.23').add()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    def test_add_a_record_with_invalid_value(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='A', value='invalid').add()
        self.assertEqual(cm.exception.args, ('value', mock.ANY))

    def test_add_a_record_without_valid_dnszone(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='A', value='192.0.2.23').add()
        self.assertEqual(cm.exception.args, ('name', mock.ANY))

    def test_add_a_record_without_valid_subnet(self):
        # Given a database with a Subnet and a DnsZone
        subnet = Subnet(ip_cidr='10.255.0.0/16').add()
        DnsZone(name='example.com', subnets=[subnet]).add()
        # When adding a DnsRecord
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='A', value='192.0.2.23').add()
        self.assertEqual(cm.exception.args, ('value', mock.ANY))

    def test_add_aaaa_record(self):
        # Given an empty database
        subnet = Subnet(ip_cidr='2002:0:0:1234::/64')
        DnsZone(name='example.com', subnets=[subnet]).add()
        # When adding a DnsRecord
        DnsRecord(name='foo.example.com', type='AAAA', value='2002::1234:abcd:ffff:c0a9:101').add()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    def test_add_aaaa_record_with_invalid_value(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='AAAA', value='invalid').add()
        self.assertEqual(cm.exception.args, ('value', mock.ANY))

    def test_add_aaaa_record_without_valid_dnszone(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord
        # Then an error is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='AAAA', value='2002::1234:abcd:ffff:c0a7:101').add()
        self.assertEqual(cm.exception.args, ('name', mock.ANY))

    def test_add_aaaa_record_without_valid_subnet(self):
        # Given a database with a valid DNSZone
        subnet = Subnet(ip_cidr='10.0.0.0/8')
        DnsZone(name='example.com', subnets=[subnet]).add()
        # When adding a DnsRecord
        # Then an error is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='AAAA', value='2002::1234:abcd:ffff:c0a6:101').add()
        self.assertEqual(cm.exception.args, ('value', mock.ANY))

    def test_add_cname_record(self):
        # Given a DnsZone
        DnsZone(name='example.com').add()
        # When adding a DnsRecord
        DnsRecord(name='foo.example.com', type='CNAME', value='bar.example.com').add()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    def test_add_cname_record_with_invalid_value(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='CNAME', value='192.0.2.23').add()
        self.assertEqual(cm.exception.args, ('value', mock.ANY))

    def test_add_cname_record_without_valid_dnszone(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord with an invalid name
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='CNAME', value='bar.example.com').add()
        self.assertEqual(cm.exception.args, ('name', mock.ANY))

    def test_add_txt_record(self):
        # Given an empty database
        DnsZone(name='example.com').add()
        # When adding a DnsRecord
        DnsRecord(name='foo.example.com', type='TXT', value='some data').add()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    def test_add_txt_record_with_invalid_value(self):
        # Given an empty database
        DnsZone(name='examples.com').add()
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='TXT', value='').add()
        self.assertEqual(cm.exception.args, ('value', mock.ANY))

    def test_add_txt_record_without_valid_dnszone(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord
        # Then an error is raise
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='TXT', value='some data').add()
        self.assertEqual(cm.exception.args, ('name', mock.ANY))

    def test_add_ipv4_ptr_record(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord
        DnsRecord(name='255.2.0.192.in-addr.arpa', type='PTR', value='bar.example.com').add()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    def test_add_ipv6_ptr_record(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord
        DnsRecord(
            name='b.a.9.8.7.6.5.0.4.0.0.0.3.0.0.0.2.0.0.0.1.0.0.0.0.0.0.0.1.2.3.4.ip6.arpa',
            type='PTR',
            value='bar.example.com',
        ).add()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    def test_add_ipv6_ptr_uppercase(self):
        # Given an ipv6 record in uppercase
        name = 'b.a.9.8.7.6.5.0.4.0.0.0.3.0.0.0.2.0.0.0.1.0.0.0.0.0.0.0.1.2.3.4.IP6.ARPA'
        # When adding the record to the database
        DnsRecord(name=name, type='PTR', value='bar.example.com').add()
        # Then the record is added with lowercase
        self.assertEqual(name.lower(), DnsRecord.query.first().name)

    def test_add_ptr_record_with_invalid_value(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='PTR', value='192.0.2.23').add()
        self.assertEqual(cm.exception.args, ('value', mock.ANY))

    def test_add_ptr_record_with_invalid_name(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='PTR', value='foo.example.com').add()
        self.assertEqual(cm.exception.args, ('name', mock.ANY))

    def test_add_ns_record(self):
        # Given an empty database
        DnsZone(name='example.com').add()
        # When adding a DnsRecord
        DnsRecord(name='foo.example.com', type='NS', value='bar.example.com').add()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    def test_add_ns_record_with_invalid_value(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DnsRecord(name='foo.example.com', type='NS', value='192.0.2.23').add()
        self.assertEqual(cm.exception.args, ('value', mock.ANY))


class DhcpRecordTest(WebCase):
    def test_json(self):
        # Given a DnsZone
        obj = DhcpRecord(ip='2002::1234:abcd:ffff:c0a8:101', mac='00:00:5e:00:53:af').add()
        # When serializing the object to json
        data = obj.to_json()
        # Then a json representation is return
        self.assertEqual(data['ip'], '2002::1234:abcd:ffff:c0a8:101')
        self.assertEqual(data['mac'], '00:00:5e:00:53:af')

    def test_add_with_ipv4(self):
        # Given an empty database
        self.assertEqual(0, DhcpRecord.query.count())
        # When adding a DnsRecord
        DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:af').add()
        # Then a new record is created
        self.assertEqual(1, DhcpRecord.query.count())

    def test_add_with_ipv6(self):
        # Given an empty database
        self.assertEqual(0, DhcpRecord.query.count())
        # When adding a DnsRecord
        DhcpRecord(ip='2002::1234:abcd:ffff:c0a8:101', mac='00:00:5e:00:53:af').add()
        # Then a new record is created
        self.assertEqual(1, DhcpRecord.query.count())

    def test_add_with_invalid_ip(self):
        # Given an empty database
        self.assertEqual(0, DhcpRecord.query.count())
        # When adding a DnsRecord with invalid data
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DhcpRecord(ip='a.0.2.23', mac='00:00:5e:00:53:af').add()
        self.assertEqual(cm.exception.args, ('ip', mock.ANY))

    def test_add_with_invalid_mac(self):
        # Given an empty database
        self.assertEqual(0, DhcpRecord.query.count())
        # When adding a DnsRecord with invalid data
        # Then an exception is raised
        with self.assertRaises(ValueError) as cm:
            DhcpRecord(ip='192.0.2.23', mac='invalid').add()
        self.assertEqual(cm.exception.args, ('mac', mock.ANY))


class IpTest(WebCase):
    def test_ip(self):
        # Given valid DnsZone with subnet
        subnet = Subnet(ip_cidr='192.0.2.0/24').add()
        DnsZone(name='example.com', subnets=[subnet]).add()
        # Given a list of DhcpRecord and DnsRecord
        DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:bf').add()
        DhcpRecord(ip='192.0.2.24', mac='00:00:5e:00:53:df').add()
        DhcpRecord(ip='192.0.2.25', mac='00:00:5e:00:53:cf').add()
        DnsRecord(name='foo.example.com', type='A', value='192.0.2.20').add()
        DnsRecord(name='bar.example.com', type='A', value='192.0.2.23').add()
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
        DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:bf', status='deleted').add()
        # When querying list of IPs
        objs = Ip.query.order_by('ip').all()
        # Then the list is empty
        self.assertEqual(len(objs), 0)

    def test_ip_with_dns_deleted_status(self):
        # Given valid DnsZone with subnet
        subnet = Subnet(ip_cidr='192.0.2.0/24').add()
        DnsZone(name='example.com', subnets=[subnet]).add()
        # Given a deleted DnsRecord
        DnsRecord(name='foo.example.com', type='A', value='192.0.2.20', status='deleted').add()
        # When querying list of IPs
        objs = Ip.query.order_by('ip').all()
        # Then the list is empty
        self.assertEqual(len(objs), 0)

    def test_ip_get_dns_records(self):
        # Given valid DnsZone with subnet
        subnet = Subnet(ip_cidr='192.0.2.0/24').add()
        DnsZone(name='example.com', subnets=[subnet]).add()
        # Given a list of DnsRecords and DhcpRecord
        DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:bf').add()
        DnsRecord(name='bar.example.com', type='A', value='192.0.2.23').add()
        DnsRecord(name='bar.example.com', type='TXT', value='x47').add()
        # When querying list of related DnsRecord on a Ip.
        objs = Ip.query.order_by('ip').first().related_dns_records
        # Then the list include all DnsRecord matching the fqdn
        self.assertEqual(len(objs), 2)
        self.assertEqual(objs[0].name, 'bar.example.com')
        self.assertEqual(objs[1].name, 'bar.example.com')

    def test_ip_get_dhcp_records(self):
        # Given valid DnsZone with subnet
        subnet = Subnet(ip_cidr='192.0.2.0/24').add()
        DnsZone(name='example.com', subnets=[subnet]).add()
        # Given a list of DnsRecords and DhcpRecord
        DhcpRecord(ip='192.0.2.23', mac='00:00:5e:00:53:bf').add()
        DnsRecord(name='bar.example.com', type='A', value='192.0.2.23').add()
        DnsRecord(name='bar.example.com', type='TXT', value='x47').add()
        # When querying list of related DhcpRecord on a Ip.
        objs = Ip.query.order_by('ip').first().related_dhcp_records
        # Then the list include all DhcpRecord matching the fqdn
        self.assertEqual(len(objs), 1)
        self.assertEqual(objs[0].mac, '00:00:5e:00:53:bf')

    def test_ipv6_related_records(self):
        # Given a DnsZone with valid subnet
        subnet = Subnet(ip_cidr='2001:db8:85a3::/64').add()
        DnsZone(name='example.com', subnets=[subnet]).add()
        # Given a list of DnsRecords and DhcpRecord with ipv6
        DhcpRecord(ip='2001:0db8:85a3:0000:0000:8a2e:0370:7334', mac='00:00:5e:00:53:bf').add()
        DnsRecord(name='bar.example.com', type='AAAA', value='2001:0db8:85a3:0000:0000:8a2e:0370:7334').add()
        # When querying list of related DnsRecord on a Ip.
        obj = Ip.query.order_by('ip').first()
        # Then the list include all DnsRecord matching the fqdn
        self.assertEqual(len(obj.related_dhcp_records), 1)
        self.assertEqual(len(obj.related_dns_records), 1)

    def test_dns_aaaa_ipv6(self):
        # Given a DnsZone with valid subnet
        subnet = Subnet(ip_cidr='2001:db8:85a3::/64').add()
        DnsZone(name='example.com', subnets=[subnet]).add()
        # Given a DnsRecords with ipv6
        DnsRecord(name='bar.example.com', type='AAAA', value='2001:0db8:85a3:0000:0000:8a2e:0370:7334').add()
        # When querying list of related DnsRecord on a Ip.
        obj = Ip.query.order_by('ip').first()
        # Then the list include all DnsRecord matching the fqdn
        self.assertEqual(len(obj.related_dhcp_records), 0)
        self.assertEqual(len(obj.related_dns_records), 1)

    def test_dhcp_ipv6(self):
        # Given a DhcpRecord with ipv6
        DhcpRecord(ip='2001:0db8:85a3:0000:0000:8a2e:0370:7334', mac='00:00:5e:00:53:bf').add()
        # When querying list of related DhcpRecord on a Ip.
        obj = Ip.query.order_by('ip').first()
        # Then the list include all DhcpRecord matching the fqdn
        self.assertEqual(len(obj.related_dhcp_records), 1)
        self.assertEqual(len(obj.related_dns_records), 0)

    def test_related_dns_record_with_ptr_ipv4(self):
        # Given a valid PTR record
        DnsRecord(name='255.2.168.192.in-addr.arpa', type='PTR', value='bar.example.com').add()
        # When querying list of IP
        obj = Ip.query.order_by('ip').first()
        # Then is include the IP Address of the PTR record
        self.assertEqual('192.168.2.255', obj.ip)
        self.assertEqual(len(obj.related_dns_records), 1)

    def test_related_dns_record_with_ptr_ipv6(self):
        # Given a valid PTR record
        DnsRecord(
            name='b.a.9.8.7.6.5.0.4.0.0.0.3.0.0.0.2.0.0.0.1.0.0.0.0.0.0.0.1.2.3.4.ip6.arpa',
            type='PTR',
            value='bar.example.com',
        ).add()
        # When querying list of IP
        obj = Ip.query.order_by('ip').first()
        # Then is include the IP Address of the PTR record
        self.assertEqual('4321::1:2:3:4:567:89ab', obj.ip)
        self.assertEqual(len(obj.related_dns_records), 1)
