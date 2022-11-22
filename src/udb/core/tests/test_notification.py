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

import cherrypy
from parameterized import parameterized

from udb.controller.tests import WebCase
from udb.core.model import DnsRecord, DnsZone, Follower, Message, Subnet, User, Vrf


class NotificationPluginTest(WebCase):
    def setUp(self):
        cherrypy.config.update({'notification.catch_all_email': None})
        self.listener = mock.MagicMock()
        cherrypy.engine.subscribe("send_mail", self.listener.send_mail, priority=50)
        return super().setUp()

    def tearDown(self):
        cherrypy.config.update({'notification.catch_all_email': None})
        cherrypy.engine.unsubscribe("send_mail", self.listener.send_mail)
        return super().tearDown()

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
        follower = User.create(
            username='afollower', password='password', email='follower@test.com', role=User.ROLE_USER
        ).add()
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
        subnet = Subnet(ranges=['192.168.0.0/24'], name='home', vrf=vrf).add().flush()
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

    def test_with_new_catchall(self):
        # Given a catchall notification email in configuration
        cherrypy.config.update({'notification.catch_all_email': 'my@email.com'})
        # When creating a new record
        DnsZone(name='my.zone.com').add().commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        # Then a notification is sent to catchall email
        self.listener.send_mail.assert_called_once_with(
            to='my@email.com',
            subject='DNS Zone my.zone.com modified by nobody',
            message=mock.ANY,
        )

    def test_with_changes_catchall(self):
        # Given a record with followers
        follower = User.create(
            username='afollower', password='password', email='follower@test.com', role=User.ROLE_USER
        ).add()
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
        # Given a DNS Zone follower
        follower = User.create(
            username='afollower', password='password', email='follower@test.com', role=User.ROLE_USER
        ).add()
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['147.87.250.0/24'], name='its-main-4', vrf=vrf)
        record = DnsZone(name='my.zone.com', subnets=[subnet]).add().flush()
        record.add_follower(follower)
        record.commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        self.listener.send_mail.assert_called_once_with(
            to='follower@test.com',
            subject='DNS Zone my.zone.com modified by nobody',
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
            subject='DNS Record my.zone.com = 147.87.250.1(A) modified by nobody',
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
        follower = User.create(username='afollower', email='follower@test.com', role=User.ROLE_USER).add()
        Follower(user=follower, model_name='vrf', model_id=0).add().commit()
        # When an object of that type get updated (model_id = 0)
        vrf = Vrf(name='default')
        vrf.add()
        vrf.commit()
        # Then wait for task to get processed
        self.wait_for_tasks()
        # Then the follower get notified.
        self.listener.send_mail.assert_called_once_with(
            to='follower@test.com',
            subject='VRF default modified by nobody',
            message=mock.ANY,
        )
