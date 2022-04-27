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


from udb.controller import url_for
from udb.controller.tests import WebCase
from udb.core.model import DhcpRecord, DnsZone, User


class NotificationsTest(WebCase):
    def test_get_page_without_following(self):
        # Given a user not following anything
        # When browser the notifications page
        self.getPage(url_for('notifications', ''))
        self.assertStatus(200)
        # Then nothing get displayed in the list
        self.assertInBody('You are not following any record.')

    def test_get_page_with_following(self):
        # Given a user following multiple record
        user = User.query.first()
        zone = DnsZone(name='boo.com').add()
        zone.add_follower(user)
        dhcp = DhcpRecord(mac='00:00:5e:00:53:af', ip='10.255.67.12').add()
        dhcp.add_follower(user)
        # When browser the notifications page
        self.getPage(url_for('notifications', ''))
        self.assertStatus(200)
        # Then list display subscribed items
        self.assertNotInBody('You are not following any record.')
        self.assertInBody('boo.com')
        self.assertInBody('00:00:5e:00:53:af')
