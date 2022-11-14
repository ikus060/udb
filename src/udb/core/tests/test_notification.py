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

from udb.controller.tests import WebCase
from udb.core.model import DnsZone, Message, Subnet, User, Vrf


class NotificationPluginTest(WebCase):
    def setUp(self):
        cherrypy.config.update({'notification.catch_all_email': None})
        self.listener = mock.MagicMock()
        cherrypy.engine.subscribe("queue_mail", self.listener.queue_mail, priority=50)
        return super().setUp()

    def tearDown(self):
        cherrypy.config.update({'notification.catch_all_email': None})
        cherrypy.engine.unsubscribe("queue_mail", self.listener.queue_mail)
        return super().tearDown()

    def test_with_comments(self):
        # Given a record with followers
        author = User.query.filter_by(username=self.username).first()
        follower = User.create(
            username='afollower', password='password', email='follower@test.com', role=User.ROLE_USER
        ).add()
        record = DnsZone(name='my.zone.com').add().flush()
        record.add_follower(follower)
        record.commit()
        # When a comment is made on that record
        record.add_message(Message(body='This is my comment', author=author))
        record.add()
        record.commit()
        # Then notifications are sent to the followers
        self.listener.queue_mail.assert_called_once_with(
            bcc=['follower@test.com'], subject='Comment on DNS Zone my.zone.com by admin', message=mock.ANY
        )

    def test_with_changes(self):
        # Given a record with followers
        follower = User.create(
            username='afollower', password='password', email='follower@test.com', role=User.ROLE_USER
        ).add()
        record = DnsZone(name='my.zone.com').add().flush()
        record.add_follower(follower)
        record.commit()
        # When a change is made on that record
        record.notes = 'This is a modification to the notes field.'
        record.add()
        record.commit()
        # Then notifications are sent to the followers
        self.listener.queue_mail.assert_called_once_with(
            bcc=['follower@test.com'], subject='DNS Zone my.zone.com modified by nobody', message=mock.ANY
        )

    def test_with_multiple_changes_merged(self):
        # Given a record with followers
        follower = User.create(
            username='afollower', password='password', email='follower@test.com', role=User.ROLE_USER
        ).add()
        vrf = Vrf(name='default')
        subnet = Subnet(ranges=['192.168.0.0/24'], name='home', vrf=vrf).add().flush()
        subnet.add_follower(follower)
        record = DnsZone(name='my.zone.com').add().flush()
        record.add_follower(follower)
        record.commit()
        # When a change is made on that record
        record.subnets = [subnet]
        record.add()
        record.commit()
        # Then a single notification is sent to the followers
        self.listener.queue_mail.assert_called_once_with(
            bcc=['follower@test.com'],
            subject='DNS Zone my.zone.com, Subnet home modified by nobody',
            message=mock.ANY,
        )

    def test_with_new_catchall(self):
        # Given a catchall notification email in configuration
        cherrypy.config.update({'notification.catch_all_email': 'my@email.com'})
        # When creating a new record
        DnsZone(name='my.zone.com').add().commit()
        # Then a notification is sent to catchall email
        self.listener.queue_mail.assert_called_once_with(
            bcc=['my@email.com'],
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
        # Given a catchall notification email in configuration
        cherrypy.config.update({'notification.catch_all_email': 'my@email.com'})
        # When a changes is made
        record.notes = 'This is a modification to the notes field.'
        record.add()
        record.commit()
        # Then a notification is sent to catchall email
        self.listener.queue_mail.assert_called_once_with(
            bcc=['follower@test.com', 'my@email.com'],
            subject='DNS Zone my.zone.com modified by nobody',
            message=mock.ANY,
        )
