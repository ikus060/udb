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


import unittest
import unittest.mock

import cherrypy

from udb.controller.tests import WebCase
from udb.core.model import User
from udb.core.passwd import hash_password


class TestLogin(WebCase):
    login = False

    def setUp(self):
        self.listener = unittest.mock.MagicMock()
        self.listener.login.return_value = False
        self.listener.authenticate.return_value = False
        cherrypy.engine.subscribe("login", self.listener.login, priority=50)
        cherrypy.engine.subscribe("authenticate", self.listener.authenticate, priority=50)
        return super().setUp()

    def tearDown(self):
        cherrypy.engine.unsubscribe("login", self.listener.login)
        cherrypy.engine.unsubscribe("authenticate", self.listener.authenticate)
        return super().tearDown()

    def test_login_valid(self):
        # Given a valid username and password
        username = "admin"
        password = "admin123"
        User.create(username=username, password=password)
        self.session.commit()
        # When login
        self.getPage("/login/", method="POST", body={"username": username, "password": password})
        # Then user is redirect to main page
        self.assertStatus('303 See Other')
        # Then listeners was called
        self.listener.login.assert_called_once_with(username, password)
        self.listener.authenticate.assert_called_once_with(username, password)

    def test_login_with_redirect(self):
        # Given a login form submited with a redirect value.
        username = "admin"
        password = "admin"
        User.create(username=username, password=password)
        self.session.commit()
        # When trying to login
        self.getPage(
            "/login/",
            method="POST",
            body={"username": username, "password": password, "redirect": "/dnszone/"},
        )
        # Then user is redirect to the proper URL.
        self.assertStatus('303 See Other')
        self.assertHeaderItemValue("Location", self.baseurl + "/dnszone/")

    def test_login_with_invalid_redirect(self):
        # Given a login form submited with a redirect value.
        username = "admin"
        password = "admin"
        User.create(username=username, password=password)
        self.session.commit()
        # When trying to login
        self.getPage(
            "/login/",
            method="POST",
            body={"username": username, "password": password, "redirect": "invalid"},
        )
        # Then user is redirect to the proper URL.
        self.assertStatus('200 OK')
        self.assertInBody('redirect: invalid redirect url')

    def test_login_with_redirect_query_string(self):
        # Given a user redirected to login page with a query string.
        # When trying to login
        self.getPage("/login/?redirect=%2Fdnszone%2F", method="GET")
        # Then the form contains a redirect value
        self.assertStatus("200 OK")
        self.assertInBody('value="/dnszone/"')

    def test_login_with_redirect_invalid_query_string(self):
        # When a user redirected to login page with an invalid query string.
        self.getPage("/login/?redirect=invalid", method="GET")
        # Then the form contains the invalid redirect value
        self.assertStatus("200 OK")
        self.assertNotInBody('invalid redirect url')
        self.assertInBody('value="invalid"')

    def test_login_invalid_credentials(self):
        # Given invalid credentials.
        username = "myusername"
        password = "mypassword"
        User.create(username=username, password=password)
        self.session.commit()
        # When trying to login
        self.getPage("/login/", method="POST", body={"username": username, "password": "invalid"})
        # Then login page is displayed with an error message.
        self.assertStatus("200 OK")
        self.assertInBody("Invalid crentials")
        # Then the username field is populated
        self.assertInBody(username)
        # Then the password field is blank
        self.assertNotInBody("invalid")

    def test_login_missing_username(self):
        # Given a missing username
        username = ""
        password = "admin"
        # When sending the form to the login page.
        self.getPage("/login/", method="POST", body={"username": username, "password": password})
        # Then login page is displayed with an error message.
        self.assertStatus("200 OK")
        self.assertInBody("This field is required.")

    def test_login_already_auth(self):
        # Given a user that is already login
        username = "admin"
        password = "admin"
        User(username=username, password=hash_password(password)).add()
        self.session.commit()
        self.getPage("/login/", method='POST', body={'username': username, 'password': password})
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
        userobj = User(username=username, password=hash_password(password)).add()
        self.session.commit()
        self.getPage("/login/", method='POST', body={'username': username, 'password': password})
        self.assertStatus('303 See Other')
        self.getPage("/")
        self.assertStatus('200 OK')
        # When deleting this user from database
        userobj.delete()
        self.session.commit()
        # Then user access is refused
        self.getPage("/")
        self.assertStatus('403 Forbidden')

    def test_redirect_to_login(self):
        # When trying to access a proptected page.
        self.getPage("/")
        # Then user is redirected to login page.
        self.assertStatus('303 See Other')
        self.assertHeaderItemValue('Location', self.baseurl + '/login/')

    def test_redirect_to_login_with_url(self):
        # When trying to access a proptected page.
        self.getPage("/dnszone/")
        # Then user is redirected to login page.
        self.assertStatus('303 See Other')
        self.assertHeaderItemValue('Location', self.baseurl + '/login/?redirect=%2Fdnszone%2F')

    def test_redirect_to_login_with_url_and_qs(self):
        # When trying to access a proptected page.
        self.getPage("/dnszone/?sort=type_asc")
        # Then user is redirected to login page.
        self.assertStatus('303 See Other')
        self.assertHeaderItemValue('Location', self.baseurl + '/login/?redirect=%2Fdnszone%2F%3Fsort%3Dtype_asc')
