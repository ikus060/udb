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
from parameterized import parameterized
from selenium.common.exceptions import ElementNotInteractableException

from udb.controller import url_for
from udb.controller.tests import WebCase
from udb.core.model import User


class UserPageTest(WebCase):

    new_data = {'username': 'newuser', 'role': 'guest'}

    edit_data = {'fullname': 'My Fullname', 'role': 'guest'}

    def setUp(self):
        self.listener = mock.MagicMock()
        cherrypy.engine.subscribe("send_mail", self.listener.send_mail, priority=50)
        return super().setUp()

    def tearDown(self):
        cherrypy.engine.unsubscribe("send_mail", self.listener.send_mail)
        return super().tearDown()

    def test_get_list_page(self):
        # Given a database with a record
        User(**self.new_data).add().commit()
        # When making a query to list page
        self.getPage(url_for('user', ''))
        # Then an html page is returned with a table
        self.assertStatus(200)
        self.assertInBody('<table')

    def test_get_edit_page(self):
        # Given a database with a record
        obj = User(**self.new_data).add()
        obj.commit()
        # When querying the edit page
        self.getPage(url_for(obj, 'edit'))
        # Then a web page is return
        self.assertStatus(200)
        self.assertInBody('Save changes')

    def test_get_new_page(self):
        # Given an empty database
        # When querying the new page
        self.getPage(url_for('user', 'new'))
        # Then a web page is return
        self.assertStatus(200)
        self.assertInBody('Create')

    def test_edit(self):
        # Given a database with a record
        obj = User(**self.new_data).add()
        obj.commit()
        # When trying to update it's name
        self.getPage(url_for(obj, 'edit'), method='POST', body=self.edit_data)
        obj.expire()
        # Then user is redirected to list page
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then database is updated
        new_obj = User.query.filter_by(username=self.new_data['username']).first()
        for k, v in self.edit_data.items():
            self.assertEqual(getattr(new_obj, k), v)

    def test_edit_selenium(self):
        # Given a database with a record
        obj = User(**self.new_data).add()
        obj.commit()
        # Given a webpage
        with self.selenium() as driver:
            # When getting web page.
            driver.get(url_for(obj, 'edit'))
            # Then the web page is loaded without error.
            self.assertFalse(driver.get_log('browser'))

    def test_edit_readonly_username_selenium(self):
        # Given a database with a record
        obj = User(**self.new_data).add()
        obj.commit()
        # Given a webpage
        with self.selenium() as driver:
            # When trying to edit the username
            driver.get(url_for(obj, 'edit'))
            e = driver.find_element('xpath', "//input[@name='username']")
            with self.assertRaises(ElementNotInteractableException):
                e.send_keys('newusername')
            # Then the web page is loaded without error.
            self.assertFalse(driver.get_log('browser'))

    def test_edit_with_password(self):
        # Given a database with a record
        obj = User(**self.new_data).add()
        obj.commit()
        # When trying to update the password with strong value.
        self.getPage(url_for(obj, 'edit'), method='POST', body={'password': 'xQPyU9yNqb3e'})
        # Then user is redirected to list page
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then database is updated
        new_obj = User.query.filter_by(username=self.new_data['username']).first()
        self.assertTrue(new_obj.check_password('xQPyU9yNqb3e'))

    def test_edit_with_password_too_weak(self):
        # Given a database with a record
        obj = User(**self.new_data).add()
        obj.commit()
        # When trying to update password with a simple value.
        self.getPage(url_for(obj, 'edit'), method='POST', body={'password': 'newpassword'})
        # Then an error message is displayed
        self.assertStatus(200)
        self.assertInBody('Password too weak.')

    def test_edit_with_clear_password(self):
        # Given a database with a record
        obj = User(**self.new_data).add()
        obj.commit()
        # When trying to update it's name
        self.getPage(url_for(obj, 'edit'), method='POST', body={'clear_password': 1})
        # Then user is redirected to list page
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then database is updated
        new_obj = User.query.filter_by(username=self.new_data['username']).first()
        self.assertEqual(None, new_obj.password)

    def test_edit_timezone(self):
        # Given a database with a record
        obj = User(**self.new_data).add()
        obj.commit()
        # Whend editing the user's timezone.
        self.getPage(url_for(obj, 'edit'), method='POST', body={'timezone': 'America/Toronto'})
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then the timezone get updated.
        obj.expire()
        self.assertEqual('America/Toronto', obj.timezone)

    def test_new(self):
        # Given an empty database
        # When trying to create a new dns zone
        self.getPage(url_for('user', 'new'), method='POST', body=self.new_data)
        # Then user is redirected to list page
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for('user') + '/')
        # Then database is updated
        obj = User.query.filter_by(username=self.new_data['username']).first()
        for k, v in self.new_data.items():
            self.assertEqual(v, getattr(obj, k))

    @parameterized.expand([('enabled', 'disabled'), ('enabled', 'deleted'), ('disabled', 'enabled')])
    def test_edit_status_disabled(self, initial_status, new_status):
        # Given a database with a record
        obj = User(**self.new_data)
        obj.status = initial_status
        obj.add()
        obj.commit()
        # When trying disabled
        self.getPage(url_for('user', obj.id, 'edit'), method='POST', body={'status': new_status})
        # Then user is redirected to the edit page
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then object status is disabled
        obj.expire()
        self.assertEqual(new_status, User.query.filter_by(username=self.new_data['username']).first().status)

    def test_status_invalid(self):
        # Given a database with a record
        obj = User(**self.new_data)
        obj.add()
        obj.commit()
        # When trying enabled
        self.getPage(url_for('user', obj.id, 'edit'), method='POST', body={'status': 'invalid'})
        # Then user error is returned
        self.assertStatus(200)
        self.assertInBody('Invalid value: invalid')
        # Then object status is enabled is removed to the record
        self.assertEqual('enabled', User.query.filter_by(username=self.new_data['username']).first().status)

    def test_edit_own_status(self):
        # Given a database with admin user
        obj = User.query.first()
        self.assertEqual('admin', obj.username)
        # When trying to update our own status
        self.getPage(url_for('user', obj.id, 'edit'), method='POST', body={'status': 'disabled'})
        # Then edit page showing an error message
        self.assertStatus(200)
        self.assertInBody('A user cannot update his own status.')

    def test_edit_own_role(self):
        # Given a database with admin user
        obj = User.query.first()
        self.assertEqual('admin', obj.username)
        self.assertEqual('admin', obj.role)
        # When trying to update our own status
        self.getPage(url_for(obj, 'edit'), method='POST', body={'role': 'guest'})
        # Then user is redirected to edit page showing an error message
        self.assertStatus(200)
        self.assertInBody('A user cannot update his own role.')

    @parameterized.expand(
        [
            ({'status': 'disabled'}, 'myuser@test.com'),
            ({'role': 'admin'}, 'myuser@test.com'),
            ({'email': 'newemail@test.com'}, ['myuser@test.com', 'newemail@test.com']),
        ]
    )
    def test_user_changes_notification(self, new_body, expected_email):
        # Given a user with email
        userobj = User.create(username='myuser', email='myuser@test.com', role='user').add().commit()
        self.wait_for_tasks()
        self.listener.send_mail.reset_mock()
        # When user is updated
        self.getPage(url_for('user', userobj.id, 'edit'), method='POST', body=new_body)
        # Then user get notified
        self.wait_for_tasks()
        if isinstance(expected_email, list):
            self.assertEqual(len(expected_email), self.listener.send_mail.call_count)
            for mail in expected_email:
                self.listener.send_mail.assert_any_call(
                    to=mail,
                    subject='User myuser modified by admin',
                    message=mock.ANY,
                )
        else:
            self.listener.send_mail.assert_called_once_with(
                to=expected_email,
                subject='User myuser modified by admin',
                message=mock.ANY,
            )

    def test_new_duplicate(self):
        # Given a database with a record
        obj = User(**self.new_data)
        obj.add()
        obj.commit()
        # When trying to create the same record.
        self.getPage(url_for('user', 'new'), method='POST', body=self.new_data)
        # Then error is repported to the user.
        self.assertStatus(200)
        self.assertInBody('This username already exists.')
        # Then a link to the duplicate subnet ir provided
        self.assertInBody(url_for(obj, 'edit'))
