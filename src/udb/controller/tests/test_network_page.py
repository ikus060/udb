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

import datetime
import json
from base64 import b64encode

from parameterized import parameterized

from udb.controller import url_for
from udb.controller.tests import WebCase
from udb.core.model import DhcpRecord, DnsZone, Ip, User


class CommonTest:

    authorization = [('Authorization', 'Basic %s' % b64encode(b'admin:admin').decode('ascii'))]

    def test_get_list_page_empty(self):
        # Given a database without record
        # When making a query to list page
        self.getPage(url_for(self.base_url, ''))
        # Then an html page is returned with a table
        self.assertStatus(200)
        self.assertInBody('<table')

    def test_get_list_page(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When making a query to list page
        self.getPage(url_for(self.base_url, ''))
        # Then an html page is returned with a table
        self.assertStatus(200)
        self.assertInBody('<table')

    def test_get_edit_page(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
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
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When trying to update it's name
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body=self.edit_data)
        obj.expire()
        # Then user is redirected
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then database is updated
        new_obj = self.obj_cls.query.first()
        for k, v in self.edit_data.items():
            self.assertEqual(getattr(new_obj, k), v)

    def test_edit_with_comment(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When trying to update it's name
        body = dict(self.edit_data)
        body['body'] = 'This is my comment'
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body=body)
        obj.expire()
        # Then user is redirected
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then database is updated
        new_obj = self.obj_cls.query.first()
        for k, v in self.edit_data.items():
            self.assertEqual(getattr(new_obj, k), v)
        # Then a message is added with our comment and changes
        self.assertTrue([msg.changes for msg in new_obj.messages if msg.body == 'This is my comment'])

    def test_edit_assign_owner(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When trying to update the owner-
        payload = dict(self.new_data)
        payload['owner_id'] = User.query.first().id
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body=payload)
        obj.expire()
        # Then user is redirected
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then database is updated
        new_obj = self.obj_cls.query.first()
        self.assertEqual(new_obj.owner, User.query.first())
        # Then an audit message is displayed on edit page.
        self.getPage(url_for(obj, 'edit'))
        self.assertInBody('<i>Undefined</i> → %s' % new_obj.owner)
        # Then appropriate owner is selected in edit page
        self.assertInBody('<option selected value="%s">%s</option>' % (new_obj.owner.id, new_obj.owner))

    def test_edit_unassign_owner(self):
        # Given a database with a record assigned to a user
        obj = self.obj_cls(**self.new_data)
        obj.owner = User.query.first()
        obj.add()
        obj.commit()
        # When trying unassign
        payload = dict(self.new_data)
        payload['owner_id'] = 'None'
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body=payload)
        obj.expire()
        # Then user is redirected to list page
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then database is updated
        new_obj = self.obj_cls.query.first()
        self.assertEqual(new_obj.owner, None)

    def test_new(self):
        # Given an empty database
        # When trying to create a new dns zone
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=self.new_data)
        # Then user is redirected to list page
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(self.base_url) + '/')
        # Then database is updated
        obj = self.obj_cls.query.first()
        for k, v in self.new_data.items():
            self.assertEqual(v, getattr(obj, k))
        # Then a audit message is created
        message = obj.messages[-1]
        self.assertIsNotNone(message.changes)
        self.assertEqual('new', message.type)

    def test_post_message(self):
        # Given a a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When trying to post a message
        self.getPage(url_for(obj, 'edit'), method='POST', body={'body': 'this is my message'})
        # Then user is redirected to the edit page
        self.assertStatus(303)
        obj = self.obj_cls.query.first()
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then a new message is added to the record.
        message = obj.messages[-1]
        self.assertEqual('this is my message', message.body)
        self.assertEqual('comment', message.type)
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        self.assertAlmostEqual(message.date, now, delta=datetime.timedelta(minutes=1))
        # Then this message is displayed on edit page
        self.getPage(url_for(obj, 'edit'))
        self.assertInBody('this is my message')

    def test_follow(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When trying follow that record
        self.getPage(url_for(obj, 'follow'), method='POST', body={"user_id": 1})
        # Then user is redirected to the edit page
        self.assertStatus(303)
        obj = self.obj_cls.query.first()
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then a new follower is added to the record
        follower = obj.followers[0]
        self.assertEqual(1, follower.id)

    def test_follow_get(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When trying follow that record
        self.getPage(url_for(obj, 'follow'), method='GET')
        self.assertStatus(405)

    def test_unfollow(self):
        # Given a database with a record
        userobj = User.query.filter_by(id=1).first()
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        obj.add_follower(userobj)
        obj.commit()
        # When trying unfollow that record
        self.getPage(url_for(self.base_url, obj.id, 'unfollow'), method='POST', body={"user_id": 1})
        # Then user is redirected to the edit page
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then a follower is removed to the record
        self.assertEqual([], self.obj_cls.query.first().followers)

    def test_unfollow_get(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When trying follow that record
        self.getPage(url_for(obj, 'unfollow'), method='GET')
        self.assertStatus(405)

    @parameterized.expand([('enabled', 'disabled'), ('enabled', 'deleted'), ('disabled', 'enabled')])
    def test_edit_status(self, initial_status, new_status):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data)
        obj.status = initial_status
        obj.add()
        obj.commit()
        # When trying disabled
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body={'status': new_status})
        obj.expire()
        # Then user is redirected to the edit page
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then object status is disabled is removed to the record
        self.assertEqual(new_status, self.obj_cls.query.first().status)

    def test_edit_status_invalid(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data)
        obj.add()
        obj.commit()
        # When trying enabled
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body={'status': 'invalid'})
        # Then user an error is displayed
        self.assertStatus(200)
        self.assertInBody('Invalid value: invalid')
        # Then object status is enabled is removed to the record
        self.assertEqual('enabled', self.obj_cls.query.first().status)

    def test_get_data_json(self):
        # Given a database with record
        obj = self.obj_cls(**self.new_data)
        obj.add()
        obj.commit()
        # When requesting data.json
        self.getPage(url_for(self.base_url, 'data.json'))
        # Then json data is returned
        self.assertStatus(200)

    def test_api_list_without_credentials(self):
        # Given I don't have credentials
        # When requesting the API
        self.getPage(url_for('api', self.base_url))
        # Then a 401 error is returned
        self.assertStatus(401)

    def test_api_list(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When querying the list of records
        data = self.getJson(url_for('api', self.base_url), headers=self.authorization)
        # Then our records is part of the list
        self.assertStatus(200)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], obj.id)
        for k, v in self.new_data.items():
            self.assertEqual(data[0][k], v)

    def test_api_get(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When querying the records from API
        data = self.getJson(url_for('api', self.base_url, obj.id), headers=self.authorization)
        # Then our records is return as json
        self.assertStatus(200)
        self.assertEqual(data['id'], obj.id)
        for k, v in self.new_data.items():
            self.assertEqual(data[k], v)

    def test_api_post(self):
        # Given a valid payload
        payload = json.dumps(self.new_data)
        # When sending a POST request to the API
        data = self.getJson(
            url_for('api', self.base_url),
            headers=[('Content-Type', 'application/json'), ('Content-Length', str(len(payload)))] + self.authorization,
            method='POST',
            body=payload,
        )
        # Then a new record is created
        self.assertStatus(200)
        for k, v in self.new_data.items():
            self.assertEqual(data[k], v)

    def test_api_put(self):
        # Given a existing record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # Given a valid payload
        payload = json.dumps(self.edit_data)
        # When sending a PUT request to the API
        data = self.getJson(
            url_for('api', self.base_url, obj.id),
            headers=[('Content-Type', 'application/json'), ('Content-Length', str(len(payload)))] + self.authorization,
            method='PUT',
            body=payload,
        )
        # Then record get updated
        self.assertStatus(200)
        for k, v in self.edit_data.items():
            self.assertEqual(data[k], v)


class DhcpRecordTest(WebCase, CommonTest):

    base_url = 'dhcprecord'

    obj_cls = DhcpRecord

    new_data = {'ip': '1.2.3.4', 'mac': '02:42:d7:e4:aa:58'}

    edit_data = {'ip': '1.2.3.5', 'mac': '02:42:d7:e4:aa:67'}

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


class IPTest(WebCase):
    def test_no_owner_filter(self):
        # Given a database with records
        obj = DhcpRecord(ip='1.2.3.4', mac='02:42:d7:e4:aa:59').add()
        obj.commit()
        # When browsing IP list view
        self.getPage('/ip/')
        # Then owner filter doesn't exists
        self.assertNotInBody('Owned by anyone')
        self.assertNotInBody('Owned by me')

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
        obj = DhcpRecord(ip='1.2.3.4', mac='02:42:d7:e4:aa:59').add()
        obj.commit()
        # When browsing IP view
        ip = Ip.query.first()
        self.getPage('/ip/%s/edit' % ip.id)
        # Then no create new exists
        self.assertStatus(200)
        self.assertInBody('02:42:d7:e4:aa:59')


class RoleTest(WebCase):
    """
    Test role verification.
    """

    login = False

    authorization = [('Authorization', 'Basic %s' % b64encode(b'guest:password').decode('ascii'))]

    def setUp(self):
        super().setUp()
        user = User.create(username='guest', password='password', role=User.ROLE_GUEST).add()
        user.commit()
        self.getPage(
            "/login/", method='POST', body={'username': user.username, 'password': 'password', 'redirect': '/'}
        )
        self.assertStatus('303 See Other')

    def test_list_as_guest(self):
        # Given a 'guest' user authenticated
        # Given a DnsZone
        obj = DnsZone(name='examples.com').add()
        obj.commit()
        # When requesting list of records
        self.getPage(url_for(DnsZone, 'data.json'))
        # Then the list is available
        self.assertStatus(200)
        self.assertInBody('examples.com')

    def test_edit_as_guest(self):
        # Given a 'guest' user authenticated
        # Given a DnsZone
        zone = DnsZone(name='examples.com').add()
        zone.commit()
        # When trying to edit a record
        self.getPage(url_for(zone, 'edit'), method='POST', body={'name': 'newname.com'})
        # Then a 403 Forbidden is raised
        self.assertStatus(403)

    def test_new_as_guest(self):
        # Given a 'guest' user authenticated
        # When trying to create a record
        self.getPage(url_for('dnszone', 'new'), method='POST', body={'name': 'newname.com'})
        # Then a 403 Forbidden is raised
        self.assertStatus(403)

    def test_api_post_as_guest(self):
        # Given a valid payload
        payload = json.dumps({'name': 'newname.com'})
        # When sending a POST request to the API
        self.getPage(
            url_for('api', 'dnszone'),
            headers=[('Content-Type', 'application/json'), ('Content-Length', str(len(payload)))] + self.authorization,
            method='POST',
            body=payload,
        )
        # Then a 403 Forbidden is raised
        self.assertStatus(403)

    def test_api_put_as_guest(self):
        # Given a existing record
        obj = DnsZone(name='examples.com').add()
        obj.commit()
        # Given a valid payload
        payload = json.dumps({'name': 'newname.com'})
        # When sending a PUT request to the API
        self.getPage(
            url_for('api', 'dnszone', obj.id),
            headers=[('Content-Type', 'application/json'), ('Content-Length', str(len(payload)))] + self.authorization,
            method='PUT',
            body=payload,
        )
        # Then a 403 Forbidden is raised
        self.assertStatus(403)
