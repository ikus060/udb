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


from cmdb.controller import url_for
from cmdb.controller.tests import WebCase
from cmdb.core.model import DnsZone, Subnet, User


class CommonTest():

    def test_get_list_page(self):
        # Given the application is started
        # When making a query to list page
        self.getPage(url_for(self.base_url, ''))
        # Then an html page is returned with a table
        self.assertStatus(200)
        self.assertInBody('<table')

    def test_get_edit_page(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        # When querying the edit page
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        # Then a web page is return
        self.assertStatus(200)
        self.assertInBody('Save changes')

    def test_get_new_page(self):
        # Given an empty database
        # When querying the new page
        self.getPage(url_for(self.base_url, 'new'))
        # Then a web page is return
        self.assertStatus(200)
        self.assertInBody('Create')

    def test_edit(self):
        # Given a datavase with a record
        obj = self.obj_cls(**self.new_data).add()
        # When trying to update it's name
        self.getPage(url_for(self.base_url, obj.id, 'edit'),
                     method='POST',
                     body={'name': 'newname.com'})
        self.session.commit()
        # Then user is redirected to list page
        self.assertStatus(303)
        # Then database is updated
        self.assertEqual('newname.com', self.obj_cls.query.first().name)

    def test_new(self):
        # Given an empty database
        # When trying to create a new dns zone
        self.getPage(url_for(self.base_url, 'new'),
                     method='POST',
                     body=self.new_data)
        self.session.commit()
        # Then user is redirected to list page
        self.assertStatus(303)
        # Then database is updated
        obj = self.obj_cls.query.first()
        for k, v in self.new_data.items():
            self.assertEqual(v, getattr(obj, k))

    def test_post_message(self):
        # Given a a database with a record
        obj = self.obj_cls(**self.new_data).add()
        # When trying to post a message
        self.getPage(url_for(self.base_url, obj.id, 'post'),
                     method='POST',
                     body={'body': 'this is my message'})
        # Then user is redirected to the edit page
        self.assertStatus(303)
        # Then a ne message is added to the record.
        message = self.obj_cls.query.first().messages[0]
        self.assertEqual('this is my message', message.body)

    def test_follow(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        # When trying follow that record
        self.getPage(url_for(self.base_url, obj.id, 'follow', 1),
                     method='POST')
        # Then user is redirected to the edit page
        self.assertStatus(303)
        # Then a new follower is added to the record
        follower = self.obj_cls.query.first().followers[0]
        self.assertEqual(1, follower.id)

    def test_unfollow(self):
        # Given a database with a record
        userobj = User.query.filter_by(id=1).first()
        obj = self.obj_cls(**self.new_data)
        obj.followers.append(userobj)
        obj.add()
        # When trying unfollow that record
        self.getPage(url_for(self.base_url, obj.id, 'unfollow', 1),
                     method='POST')
        # Then user is redirected to the edit page
        self.assertStatus(303)
        # Then a follower is removed to the record
        self.assertEqual([], self.obj_cls.query.first().followers)


class DnsZoneTest(WebCase, CommonTest):

    base_url = 'dnszone'

    new_data = {'name': 'examples.com'}

    obj_cls = DnsZone

    def test_edit_invalid(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        # When trying to update it's name
        self.getPage(url_for(self.base_url, obj.id, 'edit'),
                     method='POST',
                     body={'name': 'invalid new name'})
        self.session.commit()
        # Then edit page is displayed with an error message
        self.assertStatus(200)
        self.assertInBody('Invalid FQDN')


class SubnetTest(WebCase, CommonTest):

    base_url = 'subnet'

    obj_cls = Subnet

    new_data = {'ip_cidr': '192.168.0.1/24'}

    def test_edit_invalid(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        # When trying to update it's name
        self.getPage(url_for(self.base_url, obj.id, 'edit'),
                     method='POST',
                     body={'ip_cidr': 'invalid cidr'})
        self.session.commit()
        # Then edit page is displayed with an error message
        self.assertStatus(200)
        self.assertInBody('Invalid subnet')
