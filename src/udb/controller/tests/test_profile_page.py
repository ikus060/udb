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

from unittest.mock import MagicMock

import cherrypy

from udb.controller import url_for
from udb.controller.tests import WebCase
from udb.core.model import User


class ProfileTest(WebCase):
    def test_get_page(self):
        # Given a login user
        obj = User.query.filter_by(username=self.username).first()
        obj.fullname = 'Administrator'
        obj.email = 'admin@example.com'
        self.session.add(obj)
        self.session.commit()
        # When querying the profile page
        self.getPage(url_for('profile', ''))
        # Then My profile information is displayed
        self.assertStatus(200)
        self.assertInBody('Administrator')
        self.assertInBody('admin@example.com')
        self.assertNotInBody('User profile updated successfully.')

    def test_update_profile(self):
        # Given a user
        # When updating my profile information
        self.getPage(
            url_for('profile', ''), method='POST', body={'fullname': 'New Name', 'email': 'newmail@ikus-soft.com'}
        )
        self.assertStatus(303)
        self.assertHeaderItemValue("Location", self.baseurl + "/profile/")
        # Then the user is updated
        self.getPage(url_for('profile', ''))
        self.assertInBody('User profile updated successfully.')
        # Then the information is updated in database
        obj = User.query.filter_by(username='admin').first()
        self.assertEqual('New Name', obj.fullname)
        self.assertEqual('newmail@ikus-soft.com', obj.email)

    def test_update_profile_username(self):
        # Given a user
        # When trying to update the username
        self.getPage(url_for('profile', ''), method='POST', body={'username': 'newusername'})
        self.assertStatus(303)
        self.assertHeaderItemValue("Location", self.baseurl + "/profile/")
        # Then the username is not updated
        obj = User.query.filter_by(username='newusername').first()
        self.assertIsNone(obj)
        self.getPage(url_for('profile', ''))
        self.assertInBody('User profile updated successfully.')

    def test_update_with_invalid_email(self):
        # Given a user
        # When trying to update profile with invalid email
        self.getPage(url_for('profile', ''), method='POST', body={'email': 'invalid email'})
        # Then an error is return to the user
        self.assertStatus(200)
        self.assertInBody('Invalid email address.')
        self.assertNotInBody('User profile updated successfully.')

    def test_change_password(self):
        # Given a user
        # When updating the password
        self.getPage(
            url_for('profile', ''),
            method='POST',
            body={
                'current_password': self.password,
                'new_password': 'xQPyU9yNqb3e',
                'password_confirmation': 'xQPyU9yNqb3e',
            },
        )
        self.assertStatus(303)
        self.assertHeaderItemValue("Location", self.baseurl + "/profile/")
        # Then changes are updated in database
        obj = User.query.filter_by(username=self.username).first()
        self.assertTrue(obj.check_password('xQPyU9yNqb3e'))
        self.getPage(url_for('profile', ''))
        self.assertInBody('User profile updated successfully.')

    def test_change_password_with_confimation_missing(self):
        # Given a user
        obj = User.query.filter_by(username=self.username).first()
        current_password = obj.password
        # When updating password with the wrong confirmation
        self.getPage(
            url_for('profile', ''),
            method='POST',
            body={'current_password': self.password, 'new_password': 'newvalue', 'password_confirmation': ''},
        )
        self.assertStatus(200)
        # Then an error is displayed to the user
        self.assertInBody('Confirmation password is missing.')
        self.assertNotInBody('User profile updated successfully.')
        # Then database was not updated
        obj = User.query.filter_by(username=self.username).first()
        self.assertEqual(current_password, obj.password)

    def test_change_password_with_confimation_invalid(self):
        # Given a user
        obj = User.query.filter_by(username=self.username).first()
        current_password = obj.password
        # When updating password with the wrong confirmation
        self.getPage(
            url_for('profile', ''),
            method='POST',
            body={'current_password': self.password, 'new_password': 'newvalue', 'password_confirmation': 'invalid'},
        )
        self.assertStatus(200)
        # Then an error is displayed to the user
        self.assertInBody('The new password and its confirmation do not match.')
        self.assertNotInBody('User profile updated successfully.')
        # Then database was not updated
        obj = User.query.filter_by(username=self.username).first()
        self.assertEqual(current_password, obj.password)

    def test_change_password_with_wrong_current_password(self):
        # Given a user.
        obj = User.query.filter_by(username=self.username).first()
        current_password = obj.password
        # When updating password with the wrong current password.
        self.getPage(
            url_for('profile', ''),
            method='POST',
            body={'current_password': 'invalid', 'new_password': 'newvalue', 'password_confirmation': 'newvalue'},
        )
        self.assertStatus(200)
        # Then an error is displayed to the user.
        self.assertInBody('Current password is not valid.')
        self.assertNotInBody('User profile updated successfully.')
        # Then database was not updated
        obj = User.query.filter_by(username=self.username).first()
        self.assertEqual(current_password, obj.password)

    def test_change_password_too_weak(self):
        # Given a user
        # When updating the password
        self.getPage(
            url_for('profile', ''),
            method='POST',
            body={'current_password': self.password, 'new_password': 'test123', 'password_confirmation': 'test123'},
        )
        self.assertStatus(200)
        self.assertInBody('Password too weak.')


class ProfileTestWithExternalUser(WebCase):
    login = False

    def setUp(self):
        self.listener = MagicMock()
        cherrypy.engine.subscribe('authenticate', self.listener.authenticate, priority=40)
        return super().setUp()

    def tearDown(self):
        cherrypy.engine.unsubscribe('authenticate', self.listener.authenticate)
        return super().tearDown()

    def test_change_password_remote_user(self):
        # Given an external user authenticated
        User(username='user01').add()
        self.listener.authenticate.return_value = ('user01', {})
        self._login('user01', 'mypassword')
        # When updating the password
        self.getPage(
            url_for('profile', ''),
            method='POST',
            body={'current_password': 'mypassword', 'new_password': 'newvalue', 'password_confirmation': 'newvalue'},
        )
        self.assertStatus(200)
        # Then error message is displayed to the user
        self.assertInBody('Cannot update password for non-local user. Contact your administrator for more detail.')
        # Then password in database is still empty.
        obj = User.query.filter_by(username='user01').first()
        self.assertIsNone(obj.password)
