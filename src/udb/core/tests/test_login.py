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

from unittest.mock import MagicMock, patch

import cherrypy
import ldap3
from parameterized import parameterized

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
        User.create(username=username, password=password, role='user').commit()
        # When trying to login with those credentials
        login = cherrypy.engine.publish('login', username, password)
        # Then user is login
        self.assertTrue(login[0])
        # Then user is created in database with default role
        userobj = User.query.filter_by(username=username).first()
        self.assertEqual('user01', userobj.username)
        self.assertEqual('user', userobj.role)

    def test_login_with_invalid_challenge(self):
        # Given a user created with "raw" password.
        username = 'user01'
        password = 'password'
        User(username=username, password=password, role='user').add().commit()
        # When trying to login with those credentials
        login = cherrypy.engine.publish('login', username, password)
        # Then user is not login
        self.assertIsNone(login[0])

    def test_login_update_email(self):
        # Given valids credentials from mock
        username = 'user01'
        password = 'password'
        User.create(username=username, role='user').commit()
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
        User.create(username=username, role='user').commit()
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
        User.create(username='user01', password='password', role='user').commit()
        # When trying to login with those credentials
        login = cherrypy.engine.publish('login', 'invalid', 'password')
        # Then user is login
        self.assertFalse(login[0])

    def test_login_with_invalid_password(self):
        # Given a valid user in database
        User.create(username='user01', password='password', role='user').commit()
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
        # Then user is created in database with default role guest
        userobj = User.query.filter_by(username=username).first()
        self.assertEqual('user01', userobj.username)
        self.assertEqual('guest', userobj.role)

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
        self.assertEqual('admin', userobj.role)


class LdapLoginAbstractTest(WebCase):
    def setUp(self) -> None:
        self.server = ldap3.Server('my_fake_server')
        self.conn = ldap3.Connection(self.server, client_strategy=ldap3.MOCK_SYNC)
        self.patcher = patch('ldap3.Connection', return_value=self.conn)
        self.patcher.start()
        return super().setUp()

    def tearDown(self) -> None:
        self.patcher.stop()
        return super().tearDown()


class LoginWithLdap(LdapLoginAbstractTest):

    default_config = {
        'ldap-uri': '__default__',
        'ldap-base-dn': 'dc=example,dc=org',
        'ldap-fullname-attribute': 'displayName',
        'ldap-email-attribute': 'email',
        'add-missing-user': 'true',
    }

    def test_login_valid(self):
        # Given an LDAP server with a user
        self.conn.strategy.add_entry(
            'cn=user01,dc=example,dc=org',
            {
                'displayName': ['MyUsername'],
                'userPassword': 'password1',
                'uid': ['user01'],
                'objectClass': ['person', 'organizationalPerson', 'inetOrgPerson', 'posixAccount'],
                'email': ['myemail@example.com'],
            },
        )
        # When user try to login with valid crendentials
        login = cherrypy.engine.publish('login', 'user01', 'password1')
        # Then user is authenticated
        self.assertTrue(login[0])
        # Then user inherit attribute from LDAP server
        self.assertEqual('MyUsername', login[0].fullname)
        self.assertEqual('myemail@example.com', login[0].email)

    def test_login_with_duplicate_email(self):
        # Given a database with a user
        User.create(username='existinguser', password='password1', role='user', email='myemail@example.com').commit()
        # Given an LDAP server with a user with the same email address
        self.conn.strategy.add_entry(
            'cn=user01,dc=example,dc=org',
            {
                'displayName': ['MyUsername'],
                'userPassword': 'password1',
                'uid': ['user01'],
                'objectClass': ['person', 'organizationalPerson', 'inetOrgPerson', 'posixAccount'],
                'email': ['myemail@example.com'],
            },
        )
        # When user try to login with valid crendentials
        login = cherrypy.engine.publish('login', 'user01', 'password1')
        # Then user is authenticated
        self.assertTrue(login[0])
        # Then user inherit fullname from LDAP Server
        self.assertEqual('MyUsername', login[0].fullname)
        # Then user email address is assigned
        self.assertEqual('myemail@example.com', login[0].email)

    def test_login_invalid(self):
        # Given an LDAP server with a user
        self.conn.strategy.add_entry(
            'cn=user01,dc=example,dc=org',
            {
                'userPassword': 'password1',
                'uid': ['user01'],
                'objectClass': ['person', 'organizationalPerson', 'inetOrgPerson', 'posixAccount'],
            },
        )
        # When user try to login with invalid crendentials
        login = cherrypy.engine.publish('login', 'user01', 'invalid')
        # Then user is not authenticated
        self.assertFalse(login[0])


class LoginWithLdapGroup(LdapLoginAbstractTest):

    default_config = {
        'ldap-uri': '__default__',
        'ldap-base-dn': 'dc=example,dc=org',
        'add-missing-user': 'true',
        'ldap-user-filter': '(objectClass=posixAccount)',
        'ldap-group-filter': '(objectClass=posixGroup)',
        'ldap-admin-group': 'admingroup',
        'ldap-dnszone-mgmt-group': 'dnsgroup',
        'ldap-subnet-mgmt-group': 'subnetgroup',
        'ldap-user-group': 'usergroup',
        'ldap-guest-group': 'guestgroup',
        'ldap-group-attribute': 'memberUid',
    }

    @parameterized.expand(
        [
            ('admingroup', 'admin'),
            ('dnsgroup', 'dnszone-mgmt'),
            ('subnetgroup', 'subnet=mgmt'),
            ('usergroup', 'user'),
            ('guestgroup', 'guest'),
        ]
    )
    def test_login_assign_role(self, member_of, expected_role):
        # Given an LDAP server with a user & group
        self.conn.strategy.add_entry(
            'cn=user01,dc=example,dc=org',
            {
                'userPassword': 'password1',
                'uid': ['user01'],
                'objectClass': ['person', 'organizationalPerson', 'inetOrgPerson', 'posixAccount'],
            },
        )
        self.conn.strategy.add_entry(
            'cn=%s,ou=Groups,dc=example,dc=org' % member_of,
            {
                'cn': [member_of],
                'memberUid': ['user01'],
                'objectClass': ['posixGroup'],
            },
        )
        # When user try to login with valid crendentials
        login = cherrypy.engine.publish('login', 'user01', 'password1')
        # Then user is authenticated
        self.assertTrue(login[0])
        # Then user is assign to expected role
        self.assertTrue(login[0].role, expected_role)

    def test_login_without_group(self):
        # Given an LDAP server with a user
        self.conn.strategy.add_entry(
            'cn=user01,dc=example,dc=org',
            {
                'userPassword': 'password1',
                'uid': ['user01'],
                'objectClass': ['person', 'organizationalPerson', 'inetOrgPerson', 'posixAccount'],
            },
        )
        # When user try to login without membership to required group
        login = cherrypy.engine.publish('login', 'user01', 'password1')
        # Then user is not authenticated
        self.assertFalse(login[0])
