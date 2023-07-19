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
from udb.core.model import DhcpRecord, DnsZone, Follower, Subnet, SubnetRange, User, Vrf


class NotificationsTest(WebCase):
    def test_get_page(self):
        # Given a user not following anything
        # When browser the notifications page
        self.getPage(url_for('notifications', ''))
        self.assertStatus(200)

    def test_get_page_with_following(self):
        # Given a user following multiple record
        user = User.query.first()
        zone = DnsZone(name='boo.com').add().commit()
        vrf = Vrf(name='default')
        Subnet(
            subnet_ranges=[
                SubnetRange(
                    '10.255.67.0/24',
                    dhcp=True,
                    dhcp_start_ip='10.255.67.1',
                    dhcp_end_ip='10.255.67.254',
                )
            ],
            vrf=vrf,
        ).add().commit()
        zone.add_follower(user)
        dhcp = DhcpRecord(mac='00:00:5e:00:53:af', ip='10.255.67.12').add().commit()
        dhcp.add_follower(user)
        dhcp.commit()
        # When browser the notifications page
        self.getPage(url_for('notifications', 'data.json'))
        self.assertStatus(200)
        # Then list display subscribed items
        self.assertInBody('boo.com')
        self.assertInBody('00:00:5e:00:53:af')

    def test_subscribe_all(self):
        # Given a user
        user = User.query.first()
        self.assertTrue(user)
        # When trying to subscribe to all dnszone
        self.getPage(url_for('notifications', ''), method='POST', body={'dnszone': 1})
        # Then user is redirect to notification page.
        self.assertStatus(303)
        self.assertHeaderItemValue("Location", self.baseurl + "/notifications/")
        # Then a Follower entry is created with model_id == 0
        Follower.query.all()

    def test_unfollow_all(self):
        # Given a user following multiple record
        user = User.query.first()
        zone = DnsZone(name='boo.com').add().commit()
        vrf = Vrf(name='default')
        Subnet(
            subnet_ranges=[
                SubnetRange('10.255.67.0/24', dhcp=True, dhcp_start_ip='10.255.67.1', dhcp_end_ip='10.255.67.254')
            ],
            vrf=vrf,
        ).add().commit()
        zone.add_follower(user)
        dhcp = DhcpRecord(mac='00:00:5e:00:53:af', ip='10.255.67.12').add().commit()
        dhcp.add_follower(user)
        dhcp.commit()
        # When trying to unfollow
        self.getPage(url_for('notifications', 'unfollow'), method='POST')
        self.assertStatus(303)
        self.assertHeaderItemValue("Location", self.baseurl + "/notifications/")
        # Then list of record is empty
        self.assertNotInBody('boo.com')
        self.assertNotInBody('00:00:5e:00:53:af')
