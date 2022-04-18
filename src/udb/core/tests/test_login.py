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
'''
Created on Apr. 10, 2020

@author: Patrik Dufresne
'''

from unittest.mock import MagicMock

import cherrypy

from udb.controller.tests import WebCase
from udb.core.model import User


class TestLogin(WebCase):
    def setUp(self):
        self.listener = MagicMock()
        self.listener.authenticate.return_value = False
        cherrypy.engine.subscribe("authenticate", self.listener.authenticate, priority=50)
        return super().setUp()

    def tearDown(self):
        cherrypy.engine.unsubscribe("authenticate", self.listener.authenticate)
        return super().tearDown()

    def test_login(self):
        # Given valids credentials from database
        username = 'user01'
        password = 'password'
        User.create(username=username, password=password, role=User.ROLE_USER)
        self.session.commit()
        # When trying to login with those credentials
        login = cherrypy.engine.publish('login', username, password)
        # Then user is login
        self.assertTrue(login[0])
        # Then user is created in database with default role
        userobj = User.query.filter_by(username=username).first()
        self.assertEqual('user01', userobj.username)
        self.assertEqual(User.ROLE_USER, userobj.role)

    def test_login_update_email(self):
        # Given valids credentials from mock
        username = 'user01'
        password = 'password'
        User.create(username=username, role=User.ROLE_USER)
        self.listener.authenticate.return_value = ('user01', {'_email': 'john@test.com'})
        # When trying to login with those credentials
        login = cherrypy.engine.publish('login', username, password)
        # Then user is login
        self.assertTrue(login[0])
        # Then user is created in database with default role
        userobj = User.query.filter_by(username=username).first()
        self.assertEqual('user01', userobj.username)
        self.assertEqual('john@test.com', userobj.email)

    def test_login_update_fullname(self):
        # Given valids credentials from mock
        username = 'user01'
        password = 'password'
        User.create(username=username, role=User.ROLE_USER)
        self.listener.authenticate.return_value = ('user01', {'_fullname': 'John Kennedy'})
        # When trying to login with those credentials
        login = cherrypy.engine.publish('login', username, password)
        # Then user is login
        self.assertTrue(login[0])
        # Then user is created in database with default role
        userobj = User.query.filter_by(username=username).first()
        self.assertEqual('user01', userobj.username)
        self.assertEqual('John Kennedy', userobj.fullname)

    def test_login_with_invalid_username(self):
        # Given a valid user in database
        User.create(username='user01', password='password', role=User.ROLE_USER)
        self.session.commit()
        # When trying to login with those credentials
        login = cherrypy.engine.publish('login', 'invalid', 'password')
        # Then user is login
        self.assertFalse(login[0])

    def test_login_with_invalid_password(self):
        # Given a valid user in database
        User.create(username='user01', password='password', role=User.ROLE_USER)
        self.session.commit()
        # When trying to login with those credentials
        login = cherrypy.engine.publish('login', 'user01', 'invalid')
        # Then user is login
        self.assertFalse(login[0])


class TestLoginWithAddMissing(WebCase):

    default_config = {'add-missing-user': True}

    def setUp(self):
        self.listener = MagicMock()
        self.listener.authenticate.return_value = False
        cherrypy.engine.subscribe("authenticate", self.listener.authenticate, priority=50)
        return super().setUp()

    def tearDown(self):
        cherrypy.engine.unsubscribe("authenticate", self.listener.authenticate)
        return super().tearDown()

    def test_login(self):
        # Given valids credentials from mock
        username = 'user01'
        password = 'password'
        self.listener.authenticate.return_value = ('user01', {})
        # When trying to login with those credentials
        login = cherrypy.engine.publish('login', username, password)
        # Then user is login
        self.assertTrue(login[0])
        # Then user is created in database with default role
        userobj = User.query.filter_by(username=username).first()
        self.assertEqual('user01', userobj.username)
        self.assertEqual(User.ROLE_GUEST, userobj.role)

    def test_login_with_email_and_fullname(self):
        # Given valids credentials from mock with email and fullname
        username = 'user01'
        password = 'password'
        self.listener.authenticate.return_value = ('user01', {'_email': 'john@test.com', '_fullname': 'John Kennedy'})
        # When trying to login with those credentials
        login = cherrypy.engine.publish('login', username, password)
        # Then user is login
        self.assertTrue(login[0])
        # Then user is created in database with email and fullname
        userobj = User.query.filter_by(username=username).first()
        self.assertEqual('user01', userobj.username)
        self.assertEqual('john@test.com', userobj.email)
        self.assertEqual('John Kennedy', userobj.fullname)


class TestLoginWithAddMissingAndRole(WebCase):

    default_config = {
        'add-missing-user': True,
        'add-user-default-role': 'admin',
    }

    def setUp(self):
        self.listener = MagicMock()
        self.listener.authenticate.return_value = False
        cherrypy.engine.subscribe("authenticate", self.listener.authenticate, priority=50)
        return super().setUp()

    def tearDown(self):
        cherrypy.engine.unsubscribe("authenticate", self.listener.authenticate)
        return super().tearDown()

    def test_login(self):
        # Given valids credentials from mock
        username = 'user01'
        password = 'password'
        self.listener.authenticate.return_value = ('user01', {})
        # When trying to login with those credentials
        login = cherrypy.engine.publish('login', username, password)
        # Then user is login
        self.assertTrue(login[0])
        # Then user is created in database with default role
        userobj = User.query.filter_by(username=username).first()
        self.assertEqual('user01', userobj.username)
        self.assertEqual(User.ROLE_ADMIN, userobj.role)
