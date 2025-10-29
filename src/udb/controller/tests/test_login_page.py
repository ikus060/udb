# udb, A web interface to manage IT network
# Copyright (C) 2022-2025 IKUS Software inc.
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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


import cherrypy
from parameterized import parameterized, parameterized_class

from udb.controller.tests import WebCase
from udb.core.model import User
from udb.core.passwd import hash_password


class TestLogin(WebCase):
    login = False

    def test_login_valid(self):
        # Given a valid username and password
        username = "admin"
        password = "admin123"
        User.create(username=username, password=password).commit()
        # When login
        self.getPage("/login/", method="POST", body={"login": username, "password": password})
        # Then user is redirect to main page
        self.assertStatus('303 See Other')

    def test_login_case_insensitive(self):
        # Given a user
        # Given a valid username and password
        username = "aDmiN"
        password = "admin123"
        User.create(username=username, password=password).commit()
        # When login
        self.getPage("/login/", method="POST", body={"login": "AdMin", "password": password})
        # Then user is redirect to main page
        self.assertStatus('303 See Other')

    def test_login_with_redirect(self):
        # Given a login form submited with a redirect value.
        username = "admin"
        password = "admin"
        User.create(username=username, password=password).commit()
        # When redirected to login from another page
        self.getPage("/dnszone/")
        self.assertStatus(303)
        self.assertHeaderItemValue("Location", self.baseurl + "/login/")
        # When trying to login
        self.getPage(
            "/login/",
            method="POST",
            body={"login": username, "password": password},
        )
        # Then user is redirect to the proper URL.
        self.assertStatus('303 See Other')
        self.assertHeaderItemValue("Location", self.baseurl + "/dnszone/")

    def test_login_invalid_credentials(self):
        # Given invalid credentials.
        username = "myusername"
        password = "mypassword"
        User.create(username=username, password=password).commit()
        # When trying to login
        self.getPage("/login/", method="POST", body={"login": username, "password": "invalid"})
        # Then login page is displayed with an error message.
        self.assertStatus("200 OK")
        self.assertInBody("Invalid credentials")
        # Then the username field is populated
        self.assertInBody(username)
        # Then the password field is blank
        self.assertNotInBody("invalid")

    def test_login_missing_username(self):
        # Given a missing username
        username = ""
        password = "admin"
        # When sending the form to the login page.
        self.getPage("/login/", method="POST", body={"login": username, "password": password})
        # Then login page is displayed with an error message.
        self.assertStatus("200 OK")
        self.assertInBody("This field is required.")

    def test_login_already_auth(self):
        # Given a user that is already login
        username = "admin"
        password = "admin"
        User(username=username, password=hash_password(password)).add().commit()
        self.getPage("/login/", method='POST', body={'login': username, 'password': password})
        self.assertStatus('303 See Other')
        self.assertHeaderItemValue("Location", self.baseurl + "/")
        self.getPage("/dashboard/")
        self.assertStatus('200 OK')
        # When trying to query the login page.
        self.getPage("/login/")
        # Then user is redirect to main page
        self.assertStatus('303 See Other')
        self.assertHeaderItemValue("Location", self.baseurl + "/")

    def test_login_with_deleted_user(self):
        # Given an authentication user
        username = 'myuser'
        password = 'mypassword'
        userobj = User(username=username, password=hash_password(password)).add().commit()
        self.getPage("/login/", method='POST', body={'login': username, 'password': password})
        self.assertStatus('303 See Other')
        self.assertHeaderItemValue("Location", self.baseurl + "/")
        self.getPage("/dashboard/")
        self.assertStatus('200 OK')
        # When deleting this user from database
        userobj.delete()
        userobj.commit()
        # Then user is redirected to login page
        self.getPage("/")
        self.assertStatus('303 See Other')
        self.assertHeaderItemValue("Location", self.baseurl + "/login/")

    def test_redirect_to_login(self):
        # When trying to access a proptected page.
        self.getPage("/")
        # Then user is redirected to login page.
        self.assertStatus('303 See Other')
        self.assertHeaderItemValue('Location', self.baseurl + '/login/')

    def test_logout(self):
        # Given an unauthenticated user.
        # When trying to access the logout page.
        self.getPage("/logout", method="POST")
        # Then user is redirect to login page
        self.assertStatus('303 See Other')
        self.assertHeaderItemValue('Location', self.baseurl + '/')

    def test_login_logout(self):
        # Given a authenticated user
        self._login()
        self.getPage("/dashboard/")
        self.assertStatus('200 OK')
        # When trying to access the logout page.
        self.getPage("/logout", method="POST")
        # Then user is redirect to login page
        self.assertStatus('303 See Other')
        self.assertHeaderItemValue('Location', self.baseurl + '/')

    @parameterized.expand(
        [
            (User.STATUS_DELETED,),
            (User.STATUS_DISABLED,),
        ]
    )
    def test_login_not_enabled_user(self, user_status):
        # Given an existing user logged in
        username = "patrik"
        password = "test123"
        userobj = User.create(username=username, password=password).commit()
        self.getPage("/login/", method="POST", body={"login": username, "password": password})
        self.assertStatus('303 See Other')
        self.getPage("/dashboard/")
        self.assertStatus(200)
        # When user get deleted
        userobj.status = user_status
        userobj.add().commit()
        # Then user is redirected to login page.
        self.getPage("/dashboard/")
        self.assertStatus('303 See Other')
        self.assertHeaderItemValue('Location', self.baseurl + '/login/')


@parameterized_class(
    [
        {"default_config": {'rate-limit': 5}},
        {"default_config": {'rate-limit': 5, 'rate-limit-dir': '/tmp'}},
    ]
)
class TestLoginRateLimit(WebCase):
    login = False

    def setUp(self):
        cherrypy.tools.ratelimit.reset()
        return super().setUp()

    def tearDown(self):
        cherrypy.tools.ratelimit.reset()
        return super().tearDown()

    def test_login_rate_limit(self):
        # Given an anonymous user
        # When submiting invalid credentials
        for i in range(0, 5):
            self.getPage("/login/", method="POST", body={"login": 'username', "password": 'invalid'})
            self.assertStatus(200)
        # Then IP address get blocked
        self.getPage("/login/", method="POST", body={"login": 'username', "password": 'invalid'})
        self.assertStatus(429)
