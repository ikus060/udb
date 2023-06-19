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
from udb.core.model import DhcpRecord, Mac, Subnet, User, Vrf


class MacPageTest(WebCase):
    def setUp(self):
        super().setUp()
        # Given a database with a subnet.
        vrf = Vrf(name='default')
        Subnet(ranges=['1.2.3.0/24'], vrf=vrf, dhcp=True).add().commit()

    def test_no_deleted_filter(self):
        # Given a database with records
        obj = DhcpRecord(ip='1.2.3.4', mac='02:42:d7:e4:aa:59').add()
        obj.commit()
        # When browsing Mac list view
        self.getPage('/mac/')
        # Then no deleted filter exists
        self.assertNotInBody('Hide deleted')
        self.assertNotInBody('Show Deleted')

    def test_no_create_new(self):
        # Given a database with records
        obj = DhcpRecord(ip='1.2.3.4', mac='02:42:d7:e4:aa:59').add()
        obj.commit()
        # When browsing MAC list view
        self.getPage('/mac/')
        # Then no create new exists
        self.assertNotInBody('Create Mac')

    def test_edit_mac(self):
        # Given a database with records
        user = User.create(username='guest', password='password', role='guest').add()
        obj = DhcpRecord(ip='1.2.3.4', mac='02:42:d7:e4:aa:59').add()
        obj.commit()
        mac = Mac.query.one()
        # When editing notes of IP
        self.getPage(
            '/mac/%s/edit' % mac.id,
            method='POST',
            body={'notes': 'This is a note', 'body': 'comments', 'owner_id': user.id},
        )
        self.assertStatus(303)
        # Then IP Record get updated
        mac.expire()
        self.assertEqual('This is a note', mac.notes)
        self.assertEqual(user.id, mac.owner_id)
        # A New message is added too.
        self.assertEqual('comments', mac.messages[-1].body)
        self.assertEqual({'owner': [None, 'guest'], 'notes': ['', 'This is a note']}, mac.messages[-1].changes)

    def test_get_data_json(self):
        # Given a database with records
        obj = DhcpRecord(ip='1.2.3.4', mac='02:42:d7:e4:aa:59').add()
        obj.commit()
        Mac.query.one()
        # When requesting data.json
        self.getPage(url_for('mac/data.json'))
        # Then json data is returned
        self.assertStatus(200)

    def test_data_json_count(self):
        # Given a database with records
        obj = DhcpRecord(ip='1.2.3.4', mac='02:42:d7:e4:aa:59').add().commit()
        obj.mac = '02:42:d7:e4:aa:ff'
        obj.commit()
        # When requesting data.json
        data = self.getJson(url_for('mac/data.json'))
        # Then json data is returned
        data['data'] = sorted(data['data'], key=lambda row: row[0])
        self.assertEqual(
            data,
            {
                'data': [
                    [1, '02:42:d7:e4:aa:59', 0, '', None, '/mac/1/edit'],
                    [2, '02:42:d7:e4:aa:ff', 1, '', None, '/mac/2/edit'],
                ]
            },
        )
