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


import unittest
import unittest.mock
from cmdb.controller.tests import WebCase
from cmdb.core.passwd import hash_password
from cmdb.core.model import User, UserLoginException


class TestLogin(WebCase):
    login = False

    @unittest.mock.patch('cmdb.core.model.User.login', return_value='admin')
    def test_login_valid(self, user_login_mock):
        # Given a valid username and password
        username = 'admin'
        password = 'admin'
        # When login
        self.getPage("/login/", method='POST',
                     body={'username': username, 'password': password})
        # Then user is redirect to main page
        self.assertStatus('303 See Other')
        user_login_mock.assert_called_once_with(username, password)

    @unittest.mock.patch('cmdb.core.model.User.login', return_value='admin')
    def test_login_with_redirect(self, user_login_mock):
        # Given a login form submited with a redirect value.
        username = 'admin'
        password = 'admin'
        # When trying to login
        self.getPage("/login/", method='POST',
                     body={'username': username, 'password': password, 'redirect': '/dnszone/'})
        # Then user is redirect to the proper URL.
        self.assertStatus('303 See Other')
        self.assertHeaderItemValue('Location', self.baseurl + '/dnszone/')
        user_login_mock.assert_called_once_with(username, password)

    def test_login_with_redirect_query_string(self):
        # Given a user redirected to login page with a query string.
        # When trying to login
        self.getPage("/login/?redirect=%2Fdnszone%2F", method='GET')
        # Then the form contains a redirect value
        self.assertStatus('200 OK')
        self.assertInBody('value="/dnszone/"')

    @unittest.mock.patch('cmdb.core.model.User.login', side_effect=UserLoginException)
    def test_login_invalid_credentials(self, user_login_mock):
        # Given invalid credentials.
        username = 'myusername'
        password = 'mypassword'
        # When trying to login
        self.getPage("/login/", method='POST',
                     body={'username': username, 'password': password})
        # Then login page is displayed with an error message.
        self.assertStatus('200 OK')
        self.assertInBody('Invalid crentials')
        user_login_mock.assert_called_once_with(username, password)
        # Then the username field is populated
        self.assertInBody(username)
        # Then the password field is blank
        self.assertNotInBody(password)

    @unittest.mock.patch('cmdb.core.model.User.login', return_value='admin')
    def test_login_missing_username(self, user_login_mock):
        # Given a missing username
        username = ''
        password = 'admin'
        # When sending the form to the login page.
        self.getPage("/login/", method='POST',
                     body={'username': username, 'password': password})
        # Then login page is displayed with an error message.
        self.assertStatus('200 OK')
        self.assertInBody('This field is required.')
        user_login_mock.assert_not_called()

    def test_login_already_auth(self):
        # Given a user that is already login
        username = 'admin'
        password = 'admin'
        User(username=username, password=hash_password(password)).add()
        self.session.commit()
        self.getPage("/login/", method='POST',
                     body={'username': username, 'password': password})
        self.assertStatus('303 See Other')
        self.getPage("/")
        self.assertStatus('200 OK')
        # When trying to query the login page.
        self.getPage("/login/")
        # Then user is redirect to main page
        self.assertStatus('303 See Other')

    def test_login_with_deleted_user(self):
        # Given an authentication user
        username = 'myuser'
        password = 'mypassword'
        userobj = User(username=username,
                       password=hash_password(password)).add()
        self.session.commit()
        self.getPage("/login/", method='POST',
                     body={'username': username, 'password': password})
        self.assertStatus('303 See Other')
        self.getPage("/")
        self.assertStatus('200 OK')
        # When deleting this user from database
        userobj.delete()
        self.session.commit()
        # Then user access is refused
        self.getPage("/")
        self.assertStatus('403 Forbidden')

    @unittest.mock.patch('cmdb.core.model.User.login', return_value='admin')
    def test_redirect_to_login(self, user_login_mock):
        # When trying to access a proptected page.
        self.getPage("/")
        # Then user is redirected to login page.
        self.assertStatus('303 See Other')
        self.assertHeaderItemValue(
            'Location', self.baseurl + '/login/?redirect=%2F')

    @unittest.mock.patch('cmdb.core.model.User.login', return_value='admin')
    def test_redirect_to_login_with_url(self, user_login_mock):
        # When trying to access a proptected page.
        self.getPage("/dnszone/")
        # Then user is redirected to login page.
        self.assertStatus('303 See Other')
        self.assertHeaderItemValue(
            'Location', self.baseurl + '/login/?redirect=%2Fdnszone%2F')

    def test_login_with_store(self):
        # Given a valid user with crendial in database
        username = 'newuser'
        password = 'mypassword'
        User(username=username, password=hash_password(password)).add()
        self.session.commit()
        # When trying to login with valid credentials
        self.getPage("/login/", method='POST',
                     body={'username': username, 'password': password})
        # Then user is logged and redirect to home page.
        self.assertStatus('303 See Other')
        self.assertHeaderItemValue('Location', self.baseurl + '/')
