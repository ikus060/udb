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
from datetime import datetime, timezone
from unittest import mock

import cherrypy
from parameterized import parameterized

from udb.controller.tests import WebCase
from udb.core.model import DnsRecord, DnsZone, Follower, Message, Subnet, SubnetRange, User, Vrf


class AbstractNotificationPluginTest(WebCase):
    def setUp(self):
        cherrypy.config.update({'notification.catch_all_email': None})
        self.listener = mock.MagicMock()
        cherrypy.engine.subscribe("send_mail", self.listener.send_mail, priority=50)
        return super().setUp()

    def tearDown(self):
        cherrypy.config.update({'notification.catch_all_email': None})
        cherrypy.engine.unsubscribe("send_mail", self.listener.send_mail)
        return super().tearDown()


class NotificationPluginTest(AbstractNotificationPluginTest):
    @parameterized.expand(
        [
            ('null', None),
            ('empty', ''),
        ]
    )
    def test_notification_with(self, unused, email):
        # Given a record with followers
        author = User.query.filter_by(username=self.username).first()
        follower = User.create(username='follower', email=email).add()
        record = DnsZone(name='my.zone.com').add().flush()
        record.add_follower(follower)
        record.commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        self.listener.send_mail.reset_mock()
        # When a comment is made on that record
        record.add_message(Message(body='This is my comment', author=author))
        record.add()
        record.commit()
        # Then wait for task to get processed
        self.wait_for_tasks()

    def test_with_comments(self):
        # Given a record with followers
        author = User.query.filter_by(username=self.username).first()
        follower = User.create(username='afollower', email='follower@test.com').add()
        record = DnsZone(name='my.zone.com').add().flush()
        record.add_follower(follower)
        record.commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        self.listener.send_mail.reset_mock()
        # When a comment is made on that record
        record.add_message(Message(body='This is my comment', author=author))
        record.add()
        record.commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        # Then two notifications are sent to the followers
        self.listener.send_mail.assert_called_once_with(
            to='follower@test.com', subject='Comment on DNS Zone my.zone.com by admin', message=mock.ANY
        )

    def test_with_changes(self):
        # Given a record with followers
        follower = User.create(username='afollower', password='password', email='follower@test.com', role='user').add()
        record = DnsZone(name='my.zone.com').add().flush()
        record.add_follower(follower)
        record.commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        self.listener.send_mail.reset_mock()
        # When a change is made on that record
        record.notes = 'This is a modification to the notes field.'
        record.add()
        record.commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        # Then notifications are sent to the followers
        self.listener.send_mail.assert_called_once_with(
            to='follower@test.com', subject='DNS Zone my.zone.com modified by nobody', message=mock.ANY
        )

    def test_with_multiple_changes_merged(self):
        # Given a record with followers
        follower1 = User.create(username='follower1', email='follower1@test.com').add()
        follower2 = User.create(username='follower2', email='follower2@test.com').add()
        vrf = Vrf(name='default')
        subnet = Subnet(subnet_ranges=[SubnetRange('192.168.0.0/24')], name='home', vrf=vrf).add().flush()
        subnet.add_follower(follower1)
        record = DnsZone(name='my.zone.com').add().flush()
        record.add_follower(follower1)
        record.add_follower(follower2)
        record.commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        self.listener.send_mail.reset_mock()
        # When a change is made on that record
        record.subnets = [subnet]
        record.add()
        record.commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        # Then a single notification is sent to the followers
        self.listener.send_mail.assert_any_call(
            to='follower1@test.com',
            subject='DNS Zone my.zone.com, Subnet home modified by nobody',
            message=mock.ANY,
        )
        self.listener.send_mail.assert_any_call(
            to='follower2@test.com',
            subject='DNS Zone my.zone.com modified by nobody',
            message=mock.ANY,
        )

    def test_with_too_many_changes(self):
        # Given a lister
        follower1 = User.create(username='follower1', email='follower1@test.com').add().commit()
        self.wait_for_tasks()
        self.listener.send_mail.reset_mock()
        # When making multiple changes
        vrf = Vrf(name='default')
        for i in range(1, 24):
            subnet = Subnet(subnet_ranges=[SubnetRange(f'192.168.{i}.0/24')], name=f'subnet {i}', vrf=vrf).add().flush()
            subnet.add_follower(follower1)
        subnet.commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        # Then a single notification is sent to the followers
        self.listener.send_mail.assert_any_call(
            to='follower1@test.com',
            subject='Subnet subnet 1, Subnet subnet 2, Subnet subnet 3, Subnet subnet 4, Subnet subnet 5 created by nobody And 18 more changes',
            message=mock.ANY,
        )
        self.assertIn("And 18 more changes", self.listener.send_mail.call_args[1]['message'])

    def test_with_new_catchall(self):
        # Given a catchall notification email in configuration
        cherrypy.config.update({'notification.catch_all_email': 'my@email.com'})
        self.wait_for_tasks()
        self.listener.send_mail.reset_mock()
        # When creating a new record
        DnsZone(name='my.zone.com').add().commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        # Then a notification is sent to catchall email
        self.listener.send_mail.assert_called_once_with(
            to='my@email.com',
            subject='DNS Zone my.zone.com created by nobody',
            message=mock.ANY,
        )

    def test_with_changes_catchall(self):
        # Given a record with followers
        follower = User.create(username='afollower', password='password', email='follower@test.com', role='user').add()
        record = DnsZone(name='my.zone.com').add().flush()
        record.add_follower(follower)
        record.commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        self.listener.send_mail.reset_mock()
        # Given a catchall notification email in configuration
        cherrypy.config.update({'notification.catch_all_email': 'my@email.com'})
        # When a changes is made
        record.notes = 'This is a modification to the notes field.'
        record.add()
        record.commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        # Then a notification is sent to catchall email
        self.listener.send_mail.assert_any_call(
            to='follower@test.com',
            subject='DNS Zone my.zone.com modified by nobody',
            message=mock.ANY,
        )
        self.listener.send_mail.assert_any_call(
            to='my@email.com',
            subject='DNS Zone my.zone.com modified by nobody',
            message=mock.ANY,
        )

    def test_with_dns_record_notify_dns_zone_followers(self):
        follower = User.create(username='follower', email='follower@test.com').add()
        vrf = Vrf(name='default').add()
        subnet = Subnet(subnet_ranges=[SubnetRange('147.87.250.0/24')], name='its-main-4', vrf=vrf).add().commit()
        self.wait_for_tasks()
        self.listener.send_mail.reset_mock()
        # Given a DNS Zone follower
        record = DnsZone(name='my.zone.com', subnets=[subnet]).add().flush()
        record.add_follower(follower)
        record.commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        self.listener.send_mail.assert_called_once_with(
            to='follower@test.com',
            subject='DNS Zone my.zone.com created by nobody',
            message=mock.ANY,
        )
        self.listener.send_mail.reset_mock()
        # When a DNS Record within that zone get created
        obj = DnsRecord(name='my.zone.com', type='A', value='147.87.250.1')
        obj.add()
        obj.commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        # Then the follower get notify
        self.listener.send_mail.assert_called_once_with(
            to='follower@test.com',
            subject='DNS Record my.zone.com = 147.87.250.1 (A) created by nobody',
            message=mock.ANY,
        )

    def test_with_dns_record_notify_dns_record_followers(self):
        follower = User.create(username='follower', email='follower@test.com').add()
        vrf = Vrf(name='default')
        subnet = Subnet(subnet_ranges=[SubnetRange('147.87.250.0/24')], name='its-main-4', vrf=vrf)
        zone = DnsZone(name='my.zone.com', subnets=[subnet]).add().flush()
        zone.commit()
        self.wait_for_tasks()
        self.listener.send_mail.reset_mock()
        # Given a DNS Record follower
        record = DnsRecord(name='my.zone.com', type='A', value='147.87.250.1').add().flush()
        record.add_follower(follower)
        record.commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        self.listener.send_mail.assert_called_once_with(
            to='follower@test.com',
            subject='DNS Record my.zone.com = 147.87.250.1 (A) created by nobody',
            message=mock.ANY,
        )
        self.listener.send_mail.reset_mock()
        # When a DNS Record within that zone get created
        obj = DnsRecord(name='1.250.87.147.in-addr.arpa', type='PTR', value='my.zone.com')
        obj.add()
        obj.commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        # Then the follower get notify
        self.listener.send_mail.assert_called_once_with(
            to='follower@test.com',
            subject='DNS Record 1.250.87.147.in-addr.arpa = my.zone.com (PTR) created by nobody',
            message=mock.ANY,
        )

    def test_with_different_followers(self):
        # Given two follower subscribed to two different record.
        follower1 = User.create(username='follower1', email='follower1@test.com').add()
        follower2 = User.create(username='follower2', email='follower2@test.com').add()
        vrf1 = Vrf(name='vrf1').add().flush()
        vrf1.add_follower(follower1)
        vrf2 = Vrf(name='vrf2').add().flush()
        vrf2.add_follower(follower2)
        vrf2.commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        self.listener.send_mail.reset_mock()
        # When updating VRF1
        vrf1.notes = 'New value'
        vrf1.add()
        vrf1.commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        # Then the follower1 get notified.
        self.listener.send_mail.assert_called_once_with(
            to='follower1@test.com',
            subject='VRF vrf1 modified by nobody',
            message=mock.ANY,
        )

    def test_with_follow_all(self):
        # Given a follower of all record of a given type Vrf
        follower = User.create(username='afollower', email='follower@test.com', role='user').add()
        Follower(user=follower, model_name='vrf', model_id=0).add().commit()
        self.wait_for_tasks()
        self.listener.send_mail.reset_mock()
        # When an object of that type get updated (model_id = 0)
        vrf = Vrf(name='default')
        vrf.add()
        vrf.commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        # Then the follower get notified.
        self.listener.send_mail.assert_called_once_with(
            to='follower@test.com',
            subject='VRF default created by nobody',
            message=mock.ANY,
        )

    def test_preferred_lang(self):
        # Given a user with preferred language as French.
        user = User.create(username='myuser', email='follower@test.com', role='user', lang='fr').add()
        Follower(user=user, model_name='vrf', model_id=0).add().commit()
        self.wait_for_tasks()
        self.listener.send_mail.reset_mock()
        # When sending notification to that user
        Vrf(name='default').add().commit()
        self.wait_for_tasks()
        # Then email is send in french
        self.listener.send_mail.assert_called_once_with(
            to='follower@test.com',
            subject='VRF default créé par personne',
            message=mock.ANY,
        )

    @parameterized.expand(
        [
            ('UTC', 'Coordinated Universal Time'),
            ('America/Toronto', 'Eastern Daylight Time'),
            ('Europe/Zurich', 'Central European Summer Time'),
        ]
    )
    def test_preferred_timezone(self, tzname, code1):
        # Given a user with preferred language as French.
        user = User.create(username='myuser', email='follower@test.com', role='user', lang='en', timezone=tzname).add()
        record = Vrf(name='default').add().flush()
        record.add_follower(user)
        record.commit()
        self.wait_for_tasks()
        self.listener.send_mail.reset_mock()
        # When a comment is made on that record
        date = datetime.utcfromtimestamp(1680111611).replace(tzinfo=timezone.utc)
        record.add_message(Message(body='This is my comment', date=date))
        record.add()
        record.commit()
        self.wait_for_tasks()
        # Then email is send
        self.listener.send_mail.assert_called_once_with(
            to='follower@test.com',
            subject='Comment on VRF default by nobody',
            message=mock.ANY,
        )
        # Date uses timezone
        message = self.listener.send_mail.call_args.kwargs['message']
        self.assertIn(code1, message)


class ExternalUrlNotificationPluginTest(AbstractNotificationPluginTest):

    default_config = {'debug': False, 'external-url': 'https://test.examples.com'}

    def test_with_external_url(self):
        # Given a catchall notification email in configuration
        cherrypy.config.update({'notification.catch_all_email': 'my@email.com'})
        self.wait_for_tasks()
        self.listener.send_mail.reset_mock()
        # When creating a new record
        DnsZone(name='my.zone.com').add().commit()
        # Then a notification is sent to catchall email
        self.wait_for_tasks()
        self.listener.send_mail.assert_called_once_with(
            to='my@email.com',
            subject='DNS Zone my.zone.com created by nobody',
            message=mock.ANY,
        )
        # Then email contains URL to header logo with external-url value
        self.assertIn('https://test.examples.com/static/header_logo', self.listener.send_mail.call_args[1]['message'])
