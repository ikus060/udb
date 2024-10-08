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
from udb.core.model import User


class CommonTest:

    authorization = [('Authorization', 'Basic %s' % b64encode(b'admin:admin').decode('ascii'))]

    # Used for POST request
    new_post = None
    new_json = None
    edit_post = None

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

    def test_get_list_with_deleted(self):
        # Given a database with existing record
        data = self.getJson(url_for(self.base_url, 'data.json'))
        count = len(data['data'])
        # Given a database with a deleted record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        obj.status = self.obj_cls.STATUS_DELETED
        obj.add().commit()
        # When making a query to list page
        data = self.getJson(url_for(self.base_url, 'data.json'))
        # Then the list contains deleted record.
        self.assertEqual(1 + count, len(data['data']))

    def test_get_list_page_selenium(self):
        # Given a webpage
        with self.selenium() as driver:
            # When getting web page.
            driver.get(url_for(self.base_url, ''))
            # Then the web page contains a table
            driver.find_element('css selector', 'table.table')
            # Then the web page is loaded without error.
            self.assertFalse(driver.get_log('browser'))

    def test_get_list_filter_selenium(self):
        # Given a database with a deleted record
        obj = self.obj_cls(**self.new_data).add().flush()
        obj.status = self.obj_cls.STATUS_DELETED
        obj.add().commit()
        with self.selenium() as driver:
            # When showing the page with default filter
            driver.get(url_for(self.base_url, ''))
            # Then the web page is loaded without error.
            self.assertFalse(driver.get_log('browser'))
            # Then the deleted record badge are hidden
            with self.assertRaises(Exception):
                driver.find_element('xpath', "//span[@class='badge bg-danger' and contains(text(), 'Deleted')]")
            # When user click on "Show Deleted" buttons
            element = driver.find_element('css selector', 'button.udb-btn-filter')
            self.assertEqual("Show Deleted", element.text)
            element.click()
            # Then the web page is loaded without error.
            self.assertFalse(driver.get_log('browser'))
            # Then the list show deleted record.
            driver.find_element('xpath', "//span[@class='badge bg-danger' and contains(text(), 'Deleted')]")

    @parameterized.expand(
        [
            ('.buttons-csv', '.csv'),
            ('.buttons-excel', '.xlsx'),
            ('.buttons-pdf', '.pdf'),
        ]
    )
    def test_get_list_download_selenium(self, btn, expected_file_ext):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        with self.selenium() as driver:
            # When user click on "more" menu & "Download CSV"
            driver.get(url_for(self.base_url, ''))
            more_menu = driver.find_element('css selector', '.udb-btn-export-menu')
            more_menu.click()
            download_btn = driver.find_element('css selector', btn)
            download_btn.click()
            # Then a file get downloaded
            fn = self.assertSeleniumDownload()
            self.assertTrue(fn.startswith('export_'))
            self.assertTrue(fn.endswith(expected_file_ext))

    def test_get_edit_page(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When querying the edit page
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        # Then a web page is return
        self.assertStatus(200)
        self.assertInBody('Save changes')

    def test_get_edit_page_selenium(self):
        # Given a database with a new record with editing
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        obj.status = self.obj_cls.STATUS_DISABLED
        obj.add()
        obj.commit()
        # Given a webpage
        with self.selenium() as driver:
            # When getting web page.
            driver.get(url_for(self.base_url, obj.id, 'edit'))
            # Then the web page contains a table
            driver.find_element('id', 'save-changes')
            # Then the web page is loaded without error.
            self.assertFalse(driver.get_log('browser'))
            # Then history section contains our modification
            driver.implicitly_wait(10)
            driver.find_element('xpath', "//*[contains(text(), 'Modified by')]")

    def test_get_new_page(self):
        # Given an empty database
        # When querying the new page
        self.getPage(url_for(self.base_url, 'new'))
        # Then a web page is return
        self.assertStatus(200)
        self.assertInBody('Create')

    def test_get_new_page_selenium(self):
        # Given a webpage
        with self.selenium() as driver:
            # When getting web page.
            driver.get(url_for(self.base_url, 'new'))
            # Then the web page contains a table
            driver.find_element('id', 'create')
            # Then the web page is loaded without error.
            self.assertFalse(driver.get_log('browser'))

    def test_edit(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When trying to update it's name
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body=(self.edit_post or self.edit_data))
        obj.expire()
        # Then user is redirected
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then database is updated
        new_obj = self.obj_cls.query.filter(self.obj_cls.id == obj.id).one()
        for k, v in self.edit_data.items():
            self.assertEqual(getattr(new_obj, k), v)

    def test_edit_with_comment(self):
        # Given a database with one record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When trying to update it's name
        body = dict(self.edit_post or self.edit_data)
        body['body'] = 'This is my comment'
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body=body)
        obj.expire()
        # Then user is redirected
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then database is updated
        new_obj = self.obj_cls.query.filter(self.obj_cls.id == obj.id).one()
        for k, v in self.edit_data.items():
            self.assertEqual(getattr(new_obj, k), v)
        # Then a message is added with our comment and changes
        self.assertTrue([msg.changes for msg in new_obj.messages if msg.body == 'This is my comment'])

    def test_edit_assign_owner(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When trying to update the owner-
        payload = dict(self.new_post or self.new_data)
        payload['owner_id'] = User.query.first().id
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body=payload)
        obj.expire()
        # Then user is redirected
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then database is updated
        new_obj = self.obj_cls.query.filter(self.obj_cls.id == obj.id).one()
        self.assertEqual(new_obj.owner, User.query.first())
        # Then an audit message is displayed on edit page.
        self.getPage(url_for(obj, 'messages'))
        self.assertInBody('%s' % new_obj.owner)
        # Then appropriate owner is selected in edit page
        self.getPage(url_for(obj, 'edit'))
        self.assertInBody('<option selected value="%s">%s</option>' % (new_obj.owner.id, new_obj.owner))

    def test_edit_unassign_owner(self):
        # Given a database with a record assigned to a user
        obj = self.obj_cls(**self.new_data)
        obj.owner = User.query.first()
        obj.add()
        obj.commit()
        # When trying unassign
        payload = dict(self.new_post or self.new_data)
        payload['owner_id'] = 'None'
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body=payload)
        obj.expire()
        # Then user is redirected to list page
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then database is updated
        obj.expire()
        self.assertEqual(obj.owner, None)

    def test_new(self):
        # Given an empty database
        # When trying to create a new dns zone
        self.getPage(url_for(self.base_url, 'new'), method='POST', body=(self.new_post or self.new_data))
        # Then user is redirected to list page
        self.assertStatus(303)
        obj = self.obj_cls.query.all()[-1]
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then database is updated
        for k, v in (self.new_json or self.new_data).items():
            self.assertEqual(v, obj.to_json()[k])
        # Then a audit message is created
        message = obj.messages[-1]
        self.assertIsNotNone(message.changes)
        self.assertEqual('new', message.type)

    def test_post_message(self):
        # Given a a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When trying to post a message
        body = dict(self.new_post or self.new_data)
        body['body'] = 'this is my message'
        self.getPage(url_for(obj, 'edit'), method='POST', body=body)
        # Then user is redirected to the edit page
        self.assertStatus(303)
        obj = self.obj_cls.query.all()[-1]
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then a new message is added to the record.
        message = obj.messages[-1]
        self.assertEqual('this is my message', message.body)
        self.assertEqual('comment', message.type)
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        self.assertAlmostEqual(message.date, now, delta=datetime.timedelta(minutes=1))
        # Then this message is displayed on edit page
        self.getPage(url_for(obj, 'messages'))
        self.assertInBody('this is my message')

    def test_follow(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When trying follow that record
        self.getPage(url_for(obj, 'follow'), method='POST', body={"user_id": 1})
        # Then user is redirected to the edit page
        self.assertStatus(303)
        obj = self.obj_cls.query.all()[-1]
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

    @parameterized.expand(
        [
            (User.STATUS_ENABLED, User.STATUS_DISABLED),
            (User.STATUS_ENABLED, User.STATUS_DELETED),
            (User.STATUS_DISABLED, User.STATUS_ENABLED),
        ]
    )
    def test_edit_status(self, initial_status, new_status):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data)
        obj.status = initial_status
        obj.add()
        obj.commit()
        # When trying disabled
        body = dict(self.new_post or self.new_data)
        body['status'] = new_status
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body=body)
        obj.expire()
        # Then user is redirected to the edit page
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then object status is disabled is removed to the record
        self.assertEqual(new_status, self.obj_cls.query.all()[-1].status)

    def test_edit_status_invalid(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data)
        obj.add()
        obj.commit()
        # When trying enabled
        body = dict(self.new_post or self.new_data)
        body['status'] = -1
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body=body)
        # Then user an error is displayed
        self.assertStatus(200)
        self.assertInBody('Invalid value: -1')
        # Then object status is enabled is removed to the record
        self.assertEqual(self.obj_cls.STATUS_ENABLED, self.obj_cls.query.first().status)

    def test_get_data_json(self):
        # Given a database
        data = self.getJson(url_for(self.base_url, 'data.json'))
        count = len(data['data'])
        # Given a database with record
        obj = self.obj_cls(**self.new_data)
        obj.add()
        obj.commit()
        # When requesting data.json
        data = self.getJson(url_for(self.base_url, 'data.json'))
        # Then data contains at least one record.
        self.assertEqual(1 + count, len(data['data']))

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
        count = self.obj_cls.query.count()
        # When querying the list of records
        data = self.getJson(url_for('api', self.base_url), headers=self.authorization)
        # Then our records is part of the list
        self.assertStatus(200)
        self.assertEqual(len(data), count)
        self.assertEqual(data[-1]['id'], obj.id)
        for k, v in (self.new_json or self.new_data).items():
            self.assertEqual(data[-1][k], v)

    def test_api_get(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When querying the records from API
        data = self.getJson(url_for('api', self.base_url, obj.id), headers=self.authorization)
        # Then our records is return as json
        self.assertStatus(200)
        self.assertEqual(data['id'], obj.id, "obj.id not equal")
        for k, v in (self.new_json or self.new_data).items():
            self.assertEqual(data[k], v, "attribute %s not equal" % k)

    def test_api_post(self):
        # Given a valid payload
        payload = json.dumps(self.new_json or self.new_data)
        # When sending a POST request to the API
        data = self.getJson(
            url_for('api', self.base_url),
            headers=[('Content-Type', 'application/json'), ('Content-Length', str(len(payload)))] + self.authorization,
            method='POST',
            body=payload,
        )
        # Then a new record is created
        self.assertStatus(200)
        for k, v in (self.new_json or self.new_data).items():
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

    def test_api_delete(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When deleting that record
        self.getPage(url_for('api', self.base_url, obj.id), method='DELETE', headers=self.authorization)
        # Then our records's status is updated
        self.assertStatus(200)
        obj.expire()
        obj = self.obj_cls.query.filter(self.obj_cls.id == obj.id).one()
        self.assertEqual(self.obj_cls.STATUS_DELETED, obj.status)

    def test_list_as_guest(self):
        # Given a 'guest' user authenticated
        user = User.create(username='guest', password='password', role='guest').add()
        user.commit()
        self.getPage("/logout", method='POST')
        self.getPage(
            "/login/", method='POST', body={'username': user.username, 'password': 'password', 'redirect': '/'}
        )
        self.assertStatus('303 See Other')
        # Given a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        count = self.obj_cls.query.count()
        # When requesting list of records
        data = self.getJson(url_for(self.base_url, 'data.json'))
        # Then the list is available
        self.assertStatus(200)
        self.assertEqual(count, len(data['data']))

    def test_edit_as_guest(self):
        # Given a 'guest' user authenticated
        user = User.create(username='guest', password='password', role='guest').add()
        user.commit()
        self.getPage("/logout", method='POST')
        self.getPage(
            "/login/", method='POST', body={'username': user.username, 'password': 'password', 'redirect': '/'}
        )
        self.assertStatus('303 See Other')
        # Given a DnsZone
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When trying to edit a record
        self.getPage(url_for(obj, 'edit'), method='POST', body=(self.edit_post or self.edit_data))
        # Then a 403 Forbidden is raised
        self.assertStatus(403)
