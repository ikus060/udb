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
from udb.core.model import DhcpRecord, Subnet, User, Vrf

from .test_common_page import CommonTest


class DhcpRecordTest(WebCase, CommonTest):

    base_url = 'dhcprecord'

    obj_cls = DhcpRecord

    new_data = {'ip': '1.2.3.4', 'mac': '02:42:d7:e4:aa:58'}

    edit_data = {'ip': '1.2.3.5', 'mac': '02:42:d7:e4:aa:67'}

    def setUp(self):
        super().setUp()
        # Generate a changes
        vrf = Vrf(name='default')
        Subnet(ranges=['1.2.3.0/24'], vrf=vrf).add().commit()

    def test_new_duplicate(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data)
        obj.add()
        obj.commit()
        # When trying to create the same record.
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=self.new_data)
        # Then error is repported to the user.
        self.assertStatus(200)
        self.assertInBody('A record already exists in database with the same value.')

    def test_edit_owner_and_notes(self):
        # Given a database with a record
        user_obj = User.query.first()
        obj = self.obj_cls(**self.new_data)
        obj.add()
        obj.commit()
        self.assertEqual(1, len(obj.messages))
        obj.expire()
        # When editing notes and owner
        self.getPage(
            url_for(self.base_url, obj.id, 'edit'),
            method='POST',
            body={'notes': 'Change me to get notification !', 'owner': user_obj.id},
        )
        # Then a single message is added to the record
        self.assertEqual(2, len(obj.messages))
