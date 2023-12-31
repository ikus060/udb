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

from parameterized import parameterized

from udb.controller.tests import WebCase


class StaticTest(WebCase):
    def test_login_bg_jgp(self):
        # Given the application is started
        # When making a query to index page
        self.getPage('/static/login_bg.jpg')
        # Then an html page is returned
        self.assertStatus(200)
        self.assertHeaderItemValue('Content-Type', 'image/jpeg')

    def test_favicon_ico(self):
        # Given the application is started
        # When making a query to index page
        self.getPage('/static/favicon')
        # Then an html page is returned
        self.assertStatus(200)
        self.assertHeaderItemValue('Content-Type', 'image/svg+xml')

    def test_header_logo(self):
        # Given the application is started
        # When making a query to index page
        self.getPage('/static/header_logo')
        # Then an html page is returned
        self.assertStatus(200)
        self.assertHeaderItemValue('Content-Type', 'image/png')

    @parameterized.expand(
        [
            '/static/bootstrap5/css/bootstrap.min.css',
            '/static/bootstrap5/js/bootstrap.min.js',
            '/static/datatables/css/buttons.dataTables.min.css',
            '/static/datatables/css/jquery.dataTables.min.css',
            '/static/datatables/css/responsive.dataTables.min.css',
            '/static/datatables/js/buttons.html5.min.js',
            '/static/datatables/js/dataTables.buttons.min.js',
            '/static/datatables/js/dataTables.responsive.min.js',
            '/static/datatables/js/jquery.dataTables.min.js',
            '/static/datatables/js/jszip.min.js',
            '/static/typeahead/jquery.typeahead.min.css',
            '/static/typeahead/jquery.typeahead.min.js',
            '/static/favicon',
            '/static/header_logo',
            '/static/jquery/jquery.min.js',
            '/static/main.css',
            '/static/main.js',
            '/static/popper.js/popper.min.js',
        ]
    )
    def test_static(self, url):
        self.getPage(url)
        self.assertStatus(200)
