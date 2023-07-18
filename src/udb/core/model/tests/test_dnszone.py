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
import datetime
from unittest import mock

import cherrypy
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from udb.controller.tests import WebCase
from udb.core.model import DnsZone, Message, Subnet, SubnetRange, User, Vrf


class DnsZoneTest(WebCase):
    def test_json(self):
        # Given a DnsZone
        obj = DnsZone(name='bfh.ch').add()
        obj.commit()
        # When serializing the object to json
        data = obj.to_json()
        # Then a json representation is return
        self.assertEqual(data['name'], 'bfh.ch')

    def test_add(self):
        # Given an empty database
        self.assertEqual(0, DnsZone.query.count())
        # When adding a new Dns Zone
        zone = DnsZone(name='bfh.ch').add()
        zone.commit()
        # then a new DnsZone entry exists in database
        self.assertEqual(1, DnsZone.query.count())
        # Then a messages was added to the zone
        self.assertEqual(1, len(zone.messages))
        self.assertEqual(1, len(zone.changes))

    def test_delete(self):
        # Given a database with a DnsZone
        self.assertEqual(0, DnsZone.query.count())
        obj = DnsZone(name='bfh.ch').add()
        obj.commit()
        self.assertEqual(1, DnsZone.query.count())
        self.assertEqual(1, Message.query.filter(Message.model_name == 'dnszone').count())
        # When trying to delete a given dns zone
        obj.delete()
        obj.commit()
        # Then the entry is removed from database
        self.assertEqual(0, DnsZone.query.count())
        # Then related messages are deleted from database
        self.assertEqual(0, Message.query.filter(Message.model_name == 'dnszone').count())

    def test_soft_delete(self):
        # Given a datavase with a DnsZone
        obj = DnsZone(name='bfh.ch').add()
        obj.commit()
        self.assertEqual(1, DnsZone.query.count())
        self.assertEqual(1, Message.query.filter(Message.model_name == 'dnszone').count())
        # When updating it's status to deleted
        obj.status = DnsZone.STATUS_DELETED
        obj.add()
        obj.commit()
        # When the object still exists in database
        self.assertEqual(1, DnsZone.query.count())
        self.assertEqual(DnsZone.STATUS_DELETED, DnsZone.query.first().status)
        # Then related messages are kept
        self.assertEqual(2, Message.query.filter(Message.model_name == 'dnszone').count())

    def test_enabled(self):
        # Given a datavase with a DnsZone
        obj = DnsZone(name='bfh.ch').add()
        obj.commit()
        self.assertEqual(1, DnsZone.query.count())
        # When updating it's status to deleted
        obj.status = DnsZone.STATUS_ENABLED
        obj.add()
        obj.commit()
        # Then the object still exists in database
        self.assertEqual(1, DnsZone.query.count())
        self.assertEqual(DnsZone.STATUS_ENABLED, DnsZone.query.first().status)

    def test_disabled(self):
        # Given a datavase with a DnsZone
        obj = DnsZone(name='bfh.ch').add()
        obj.commit()
        self.assertEqual(1, DnsZone.query.count())
        # When updating it's status to deleted
        obj.status = DnsZone.STATUS_DISABLED
        obj.add()
        obj.commit()
        # When the object still exists in database
        self.assertEqual(1, DnsZone.query.count())
        self.assertEqual(DnsZone.STATUS_DISABLED, DnsZone.query.first().status)

    def test_invalid_name(self):
        # Given an ampty database
        self.assertEqual(0, DnsZone.query.count())
        # When trying to create a new DnsZone with an invalid fqdn
        # Then an excpetion is raised
        with self.assertRaises(ValueError) as cm:
            DnsZone(name='invalid/name').add().commit()
        self.assertEqual(cm.exception.args, ('name', mock.ANY))

    def test_duplicate_name(self):
        # Given a database with an existing record
        DnsZone(name='bfh.ch').add().commit()
        self.assertEqual(1, DnsZone.query.count())
        # When trying to add a dns zone with an existing name
        # Then an exception is raised
        with self.assertRaises(IntegrityError):
            DnsZone(name='bfh.ch').add().commit()

    def test_duplicate_name_case_insensitive(self):
        # Given a database with an existing record
        DnsZone(name='bfh.ch').add().commit()
        self.assertEqual(1, DnsZone.query.count())
        # When trying to add a dns zone with an existing name
        # Then an exception is raised
        with self.assertRaises(IntegrityError):
            DnsZone(name='BFH.ch').add().commit()

    def test_update_owner(self):
        # Given a database with an existing record
        d = DnsZone(name='bfh.ch').add()
        d.commit()
        self.assertEqual(1, DnsZone.query.count())
        # When trying to update the owner
        new_user = User(username='test').add()
        d.owner = new_user
        d.add()
        d.commit()
        # Then a new message with changes is append to the object.
        messages = d.messages
        self.assertEqual(2, len(messages))
        self.assertEqual({'owner': [None, 'test']}, messages[-1].changes)

    def test_add_subnet(self):
        # Given a database with an existing record
        zone = DnsZone(name='bfh.ch').add()
        zone.commit()
        # When trying to add an allowed subnet to the dns zone
        vrf = Vrf(name='default')
        subnet = Subnet(name='test', subnet_ranges=[SubnetRange('192.168.1.0/24')], vrf=vrf).add().commit()
        zone.subnets.append(subnet)
        zone.add()
        zone.commit()
        # Then a subnet is added
        zone = DnsZone.query.first()
        subnet = Subnet.query.first()
        self.assertEqual(1, len(zone.subnets))
        self.assertEqual('test', zone.subnets[0].name)
        self.assertEqual(1, len(zone.subnets[0].dnszones))
        self.assertEqual(zone, zone.subnets[0].dnszones[0])
        # Then an audit message is created for both objects
        self.assertEqual(2, len(zone.messages))
        self.assertEqual(zone.messages[-1].changes, {'subnets': [[], ['192.168.1.0/24 (test)']]})
        self.assertEqual(2, len(subnet.messages))
        self.assertEqual(subnet.messages[-1].changes, {'dnszones': [[], ['bfh.ch']]})
        # Then subnets_count is updated
        self.assertEqual(1, zone.subnets_count)

    def test_subnets_deleted(self):
        # Given a database with a deleted subnet
        vrf = Vrf(name='default').add()
        subnet = Subnet(
            name='test', subnet_ranges=[SubnetRange('192.168.1.0/24')], status=Subnet.STATUS_DELETED, vrf=vrf
        ).add()
        zone = DnsZone(name='bfh.ch', subnets=[subnet]).add().commit()
        # When querying the list of subnets within a zone
        subnets = zone.subnets
        # Then the list doesn't include the deleted subnet
        self.assertEqual([], subnets)

    def test_get_messages(self):
        # Given a database with an existing record
        d = DnsZone(name='bfh.ch').add().commit()
        self.assertEqual(1, DnsZone.query.count())
        # When updating the owner
        new_user = User(username='test').add()
        d.owner = new_user
        d.add()
        d.commit()
        # When adding a comments
        now = datetime.datetime.now(datetime.timezone.utc)
        d.add_message(Message(body='this is a comments'))
        d.commit()
        # Then a message with type 'new' exists
        messages = d.changes
        self.assertEqual(2, len(messages))
        self.assertEqual(messages[0].changes, {'name': [None, 'bfh.ch']})
        self.assertEqual(messages[1].changes, {'owner': [None, 'test']})
        # Then a message with type 'comment' exists
        messages = d.comments
        self.assertEqual(1, len(messages))
        self.assertEqual(messages[0].changes, None)
        self.assertEqual(messages[0].body, 'this is a comments')
        self.assertAlmostEqual(messages[0].date, now, delta=datetime.timedelta(seconds=1))
        # Then the list of message contains all tre message
        messages = d.messages
        self.assertEqual(3, len(messages))

    def test_search(self):
        # Given a database with records
        main = DnsZone(name='example.com', notes='This is the main zone').add()
        science = DnsZone(name='science.example.com', notes='testing').add()
        DnsZone(name='dmz.example.com', notes='Use for DMZ').add().commit()
        # When searching for a term in notes
        records = DnsZone.query.filter(func.udb_websearch(DnsZone.search_string, 'main')).all()
        # Then a single record is returned
        self.assertEqual(main, records[0])
        # When searching for a term in name
        records = DnsZone.query.filter(func.udb_websearch(DnsZone.search_string, 'science.example.com')).all()
        # Then a single record is returned
        self.assertEqual(science, records[0])

        # When searching multiple word with wrong order
        is_postgresql = 'postgresql' in cherrypy.config.get('tools.db.uri')
        if is_postgresql:
            records = DnsZone.query.filter(func.udb_websearch(DnsZone.search_string, 'exampl science co')).all()
            # Then a single record is returned
            self.assertEqual(science, records[0])
