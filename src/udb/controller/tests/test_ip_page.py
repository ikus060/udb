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
from udb.core.model import DhcpRecord, Ip, User


class IPTest(WebCase):
    def test_no_deleted_filter(self):
        # Given a database with records
        obj = DhcpRecord(ip='1.2.3.4', mac='02:42:d7:e4:aa:59').add()
        obj.commit()
        # When browsing IP list view
        self.getPage('/ip/')
        # Then no deleted filter exists
        self.assertNotInBody('Hide deleted')
        self.assertNotInBody('Show deleted')

    def test_no_create_new(self):
        # Given a database with records
        obj = DhcpRecord(ip='1.2.3.4', mac='02:42:d7:e4:aa:59').add()
        obj.commit()
        # When browsing IP list view
        self.getPage('/ip/')
        # Then no create new exists
        self.assertNotInBody('Create IP Address')

    def test_edit_ip(self):
        # Given a database with records
        user = User.create(username='guest', password='password', role=User.ROLE_GUEST).add()
        obj = DhcpRecord(ip='1.2.3.4', mac='02:42:d7:e4:aa:59').add()
        obj.commit()
        ip = Ip.query.one()
        # When editing notes of IP
        self.getPage(
            '/ip/%s/edit' % ip.id,
            method='POST',
            body={'notes': 'This is a note', 'body': 'comments', 'owner_id': user.id},
        )
        self.assertStatus(303)
        # Then IP Record get updated
        ip.expire()
        self.assertEqual('This is a note', ip.notes)
        self.assertEqual(user.id, ip.owner_id)
        # A New message is added too.
        self.assertEqual('comments', ip.messages[-1].body)
        self.assertEqual({'owner': [None, 'guest'], 'notes': ['', 'This is a note']}, ip.messages[-1].changes)

    def test_get_data_json(self):
        # Given a database with records
        obj = DhcpRecord(ip='1.2.3.4', mac='02:42:d7:e4:aa:59').add()
        obj.commit()
        Ip.query.one()
        # When requesting data.json
        self.getPage(url_for('ip/data.json'))
        # Then json data is returned
        self.assertStatus(200)

    def test_data_json_count(self):
        # Given a database with records
        obj = DhcpRecord(ip='1.2.3.4', mac='02:42:d7:e4:aa:59').add().commit()
        obj.ip = '2.3.4.5'
        obj.commit()
        # When requesting data.json
        data = self.getJson(url_for('ip/data.json'))
        # Then json data is returned
        data['data'] = sorted(data['data'], key=lambda row: row['id'])
        self.assertEqual(
            data,
            {
                'data': [
                    {'id': 1, 'ip': '1.2.3.4', 'notes': '', 'count': 0, 'owner': None, 'url': '/ip/1/edit'},
                    {'id': 2, 'ip': '2.3.4.5', 'notes': '', 'count': 1, 'owner': None, 'url': '/ip/2/edit'},
                ]
            },
        )
