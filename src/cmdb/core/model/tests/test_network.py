# -*- coding: utf-8 -*-
# cmdb, A web interface to manage IT network CMDB
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

from cmdb.controller.tests import WebCase
from cmdb.core.model import DnsZone, Subnet, DnsRecord, DhcpRecord
from sqlalchemy.exc import IntegrityError


class DnsZoneTest(WebCase):

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

    def test_invalid_name(self):
        # Given an ampty database
        self.assertEqual(0, DnsZone.query.count())
        # When trying to create a new DnsZone with an invalid fqdn
        # Then an excpetion is raised
        with self.assertRaises(ValueError):
            DnsZone(name='invalid/name').add()

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


class SubnetTest(WebCase):

    def test_add_ipv4(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with IPV4
        Subnet(ip_cidr='192.168.1.0/24').add()
        # Then a new record is created
        self.assertEqual(1, Subnet.query.count())

    def test_add_ipv6(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with IPV6
        Subnet(ip_cidr='2002::1234:abcd:ffff:c0a8:101/64').add()
        # Then a new record is created
        self.assertEqual(1, Subnet.query.count())

    def test_invalid_ipv4(self):
        # Given an empty database
        self.assertEqual(0, Subnet.query.count())
        # When adding a Subnet with an invalid IP
        with self.assertRaises(ValueError):
            Subnet(ip_cidr='a.168.1.0/24').add()
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


class DnsRecordTest(WebCase):

    def test_add_a_record(self):
        # Given an empty database
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
        with self.assertRaises(ValueError):
            DnsRecord(name='foo.example.com', type='A', value='invalid').add()

    def test_add_cname_record(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord
        DnsRecord(name='foo.example.com', type='CNAME',
                  value='bar.example.com').add()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    def test_add_cname_record_with_invalid_value(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(ValueError):
            DnsRecord(name='foo.example.com', type='CNAME',
                      value='192.0.2.23').add()

    def test_add_txt_record(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord
        DnsRecord(name='foo.example.com', type='TXT',
                  value='some data').add()
        # Then a new record is created
        self.assertEqual(1, DnsRecord.query.count())

    def test_add_txt_record_with_invalid_value(self):
        # Given an empty database
        self.assertEqual(0, DnsRecord.query.count())
        # When adding a DnsRecord with an invalid value
        # Then an exception is raised
        with self.assertRaises(ValueError):
            DnsRecord(name='foo.example.com', type='TXT',
                      value='').add()


class DhcpRecordTest(WebCase):

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
        DhcpRecord(ip='2002::1234:abcd:ffff:c0a8:101',
                   mac='00:00:5e:00:53:af').add()
        # Then a new record is created
        self.assertEqual(1, DhcpRecord.query.count())

    def test_add_with_invalid_ip(self):
        # Given an empty database
        self.assertEqual(0, DhcpRecord.query.count())
        # When adding a DnsRecord with invalid data
        # Then an exception is raised
        with self.assertRaises(ValueError):
            DhcpRecord(ip='a.0.2.23', mac='00:00:5e:00:53:af').add()

    def test_add_with_invalid_mac(self):
        # Given an empty database
        self.assertEqual(0, DhcpRecord.query.count())
        # When adding a DnsRecord with invalid data
        # Then an exception is raised
        with self.assertRaises(ValueError):
            DhcpRecord(ip='192.0.2.23', mac='invalid').add()
