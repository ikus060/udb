# -*- coding: utf-8 -*-
# udb, A web interface to manage IT network
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

from udb.controller import url_for
from udb.controller.tests import WebCase
from udb.core.model import User


class UserTest(WebCase):

    new_data = {'username': 'newuser', 'role': 10}

    edit_data = {'fullname': 'My Fullname', 'role': 10}

    def test_get_list_page(self):
        # Given a database with a record
        User(**self.new_data).add()
        # When making a query to list page
        self.getPage(url_for('user', ''))
        # Then an html page is returned with a table
        self.assertStatus(200)
        self.assertInBody('<table')

    def test_get_list_with_sort(self):
        # Given a database with a record
        User(**self.new_data).add()
        # When making a query to list records with sorted column
        field = list(self.new_data.keys())[0]
        self.getPage(url_for('user', '', sort=field + '_asc'))
        # Then an html page is returned with a table
        self.assertStatus(200)
        self.assertInBody('<table')
        self.assertInBody(field + '_desc')

    def test_get_edit_page(self):
        # Given a database with a record
        obj = User(**self.new_data).add()
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
        # When trying to update it's name
        self.getPage(url_for(obj, 'edit'), method='POST', body=self.edit_data)
        self.session.commit()
        # Then user is redirected to list page
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for('user') + '/')
        # Then database is updated
        new_obj = User.query.filter_by(username=self.new_data['username']).first()
        for k, v in self.edit_data.items():
            self.assertEqual(getattr(new_obj, k), v)

    def test_new(self):
        # Given an empty database
        # When trying to create a new dns zone
        self.getPage(url_for('user', 'new'), method='POST', body=self.new_data)
        self.session.commit()
        # Then user is redirected to list page
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for('user') + '/')
        # Then database is updated
        obj = User.query.filter_by(username=self.new_data['username']).first()
        for k, v in self.new_data.items():
            self.assertEqual(v, getattr(obj, k))

    def test_status_disabled(self):
        # Given a database with a record
        obj = User(**self.new_data)
        obj.add()
        # When trying disabled
        self.getPage(url_for('user', obj.id, 'status', 'disabled'))
        self.session.commit()
        # Then user is redirected to the edit page
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then object status is disabled is removed to the record
        self.assertEqual('disabled', User.query.filter_by(username=self.new_data['username']).first().status)

    def test_status_delete(self):
        # Given a database with a record
        obj = User(**self.new_data)
        obj.add()
        # When trying delete
        self.getPage(url_for('user', obj.id, 'status', 'deleted'))
        self.session.commit()
        # Then user is redirected to the edit page
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then object status is delete is removed to the record
        self.assertEqual('deleted', User.query.filter_by(username=self.new_data['username']).first().status)

    def test_status_enabled(self):
        # Given a database with a record
        obj = User(**self.new_data)
        obj.status = 'disabled'
        obj.add()
        # When trying enabled
        self.getPage(url_for('user', obj.id, 'status', 'enabled'))
        self.session.commit()
        # Then user is redirected to the edit page
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        # Then object status is enabled is removed to the record
        self.assertEqual('enabled', User.query.filter_by(username=self.new_data['username']).first().status)

    def test_status_invalid(self):
        # Given a database with a record
        obj = User(**self.new_data)
        obj.add()
        # When trying enabled
        self.getPage(url_for('user', obj.id, 'status', 'invalid'))
        self.session.commit()
        # Then user is redirected to the edit page
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        self.getPage(url_for('user', obj.id, 'edit'))
        self.assertInBody('Invalid value: invalid')
        # Then object status is enabled is removed to the record
        self.assertEqual('enabled', User.query.filter_by(username=self.new_data['username']).first().status)

    def test_edit_own_status(self):
        # Given a database with admin user
        obj = User.query.first()
        self.assertEqual('admin', obj.username)
        # When trying to update our own status
        self.getPage(url_for('user', obj.id, 'status', 'disabled'))
        # Then user is redirected to edit page showing an error message
        self.assertStatus(303)
        self.assertHeaderItemValue('Location', url_for(obj, 'edit'))
        self.getPage(url_for('user', obj.id, 'edit'))
        self.assertInBody('The user cannot update his own status.')

    def test_edit_own_role(self):
        # Given a database with admin user
        obj = User.query.first()
        self.assertEqual('admin', obj.username)
        self.assertEqual(0, obj.role)
        # When trying to update our own status
        self.getPage(url_for(obj, 'edit'), method='POST', body={'role': 10})
        # Then user is redirected to edit page showing an error message
        self.assertStatus(200)
        self.assertInBody('The user cannot update his own role.')
