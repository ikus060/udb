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


from cmdb.controller.tests import WebCase


class TestLogout(WebCase):
    login = False

    def test_logout(self):
        # Given an unauthenticated user.
        # When trying to access the logout page.
        self.getPage("/logout/")
        # Then user is redirect to login page
        self.assertStatus('303 See Other')
        self.assertHeaderItemValue('Location', self.baseurl + '/login/')

    def test_login_logout(self):
        # Given a authenticated user
        self._login()
        self.getPage("/")
        self.assertStatus('200 OK')
        # When trying to access the logout page.
        self.getPage("/logout/")
        # Then user is redirect to login page
        self.assertStatus('303 See Other')
        self.assertHeaderItemValue('Location', self.baseurl + '/login/')
