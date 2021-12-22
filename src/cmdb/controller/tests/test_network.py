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

import json
from base64 import b64encode

from cmdb.controller import url_for
from cmdb.controller.tests import WebCase
from cmdb.core.model import DnsZone, Subnet, User


class CommonTest():

    authorization = [('Authorization', 'Basic %s' %
                      b64encode(b'admin:admin').decode('ascii'))]

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
                     body=self.edit_data)
        self.session.commit()
        # Then user is redirected to list page
        self.assertStatus(303)
        # Then database is updated
        new_obj = self.obj_cls.query.first()
        for k, v in self.edit_data.items():
            self.assertEqual(getattr(new_obj, k), v)

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

    def test_api_list_without_credentials(self):
        # Given I don't have credentials
        # When requesting the API
        self.getPage(url_for('api', self.base_url))
        # Then a 401 error is returned
        self.assertStatus(401)

    def test_api_list(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        # When querying the list of records
        data = self.getJson(url_for('api', self.base_url),
                            headers=self.authorization)
        # Then our records is part of the list
        self.assertStatus(200)
        self.assertEquals(len(data), 1)
        self.assertEquals(data[0]['id'], obj.id)
        for k, v in self.new_data.items():
            self.assertEquals(data[0][k], v)

    def test_api_get(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        # When querying the records from API
        data = self.getJson(url_for('api', self.base_url, obj.id),
                            headers=self.authorization)
        # Then our records is return as json
        self.assertStatus(200)
        self.assertEquals(data['id'], obj.id)
        for k, v in self.new_data.items():
            self.assertEquals(data[k], v)

    def test_api_post(self):
        # Given a valid payload
        payload = json.dumps(self.new_data)
        # When sending a POST request to the API
        data = self.getJson(url_for('api', self.base_url),
                            headers=[('Content-Type', 'application/json'),
                                     ('Content-Length', str(len(payload)))] + self.authorization,
                            method='POST', body=payload)
        # Then a new record is created
        self.assertStatus(200)
        for k, v in self.new_data.items():
            self.assertEquals(data[k], v)

    def test_api_put(self):
        # Given a existing record
        obj = self.obj_cls(**self.new_data).add()
        # Given a valid payload
        payload = json.dumps(self.edit_data)
        # When sending a PUT request to the API
        data = self.getJson(url_for('api', self.base_url, obj.id),
                            headers=[('Content-Type', 'application/json'),
                                     ('Content-Length', str(len(payload)))] + self.authorization,
                            method='PUT', body=payload)
        # Then record get updated
        self.assertStatus(200)
        for k, v in self.edit_data.items():
            self.assertEquals(data[k], v)


class DnsZoneTest(WebCase, CommonTest):

    base_url = 'dnszone'

    new_data = {'name': 'examples.com'}

    edit_data = {'name': 'this.is.a.new.value.com'}

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

    edit_data = {'ip_cidr': '192.168.100.1/24', 'vrf': 4}

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
