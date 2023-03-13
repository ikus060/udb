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


from sqlalchemy.exc import IntegrityError

from udb.controller.tests import WebCase
from udb.core.model import User


class UserTest(WebCase):
    def test_duplicate_username(self):
        # Given a database with a User
        User(username='MyUsername').add().commit()
        # When trying to add another user with the same email
        # Then an exception is raised
        with self.assertRaises(IntegrityError):
            User(username='myusername').add().commit()

    def test_duplicate_email(self):
        # Given a database with a User
        User(username='user1', email='test@example.com').add().commit()
        # When trying to add another user with the same email
        # Then an exception is raised
        with self.assertRaises(IntegrityError):
            User(username='user2', email='test@example.com').add().commit()

    def test_duplicate_email_empty(self):
        # Given a database with a User
        User(username='user1', email='').add().commit()
        # When trying to add another user with empty email
        # Then user is created without error.
        User(username='user2', email='').add().commit()

    def test_duplicate_email_none(self):
        # Given a database with a User
        User(username='user1', email=None).add().commit()
        # When trying to add another user with empty email
        # Then user is created without error.
        User(username='user2', email=None).add().commit()
