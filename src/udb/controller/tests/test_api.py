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


from base64 import b64encode

from udb.controller.tests import WebCase


class TestApiPage(WebCase):
    authorization = [('Authorization', 'Basic %s' % b64encode(b'admin:admin').decode('ascii'))]

    def test_index(self):
        # Given the application is started
        # When making a query to index page
        self.getPage('/api/', headers=self.authorization)
        # Then status is returned
        self.assertStatus(200)
        self.assertBody('{"status": "OK"}')

    def test_api_error(self):
        # Given the application is started
        # When making an invalid query to api page
        self.getPage('/api/invalid', headers=self.authorization)
        # Then status is returned
        self.assertStatus(404)
        self.assertInBody('{"message": "Nothing matches the given URI", "status": "404 Not Found"}')
