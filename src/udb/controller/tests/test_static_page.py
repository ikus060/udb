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
            '/static/components/CustomDatatable.js',
            '/static/components/Datatable.css',
            '/static/components/Datatable.js',
            '/static/components/Typeahead.js',
            '/static/components/vendor/bootstrap5/css/bootstrap.min.css',
            '/static/components/vendor/bootstrap5/js/bootstrap.min.js',
            '/static/components/vendor/datatables-extensions/Buttons/css/buttons.dataTables.min.css',
            '/static/components/vendor/datatables-extensions/Buttons/js/buttons.html5.min.js',
            '/static/components/vendor/datatables-extensions/Buttons/js/dataTables.buttons.min.js',
            '/static/components/vendor/datatables-extensions/FixedHeader/css/fixedHeader.dataTables.css',
            '/static/components/vendor/datatables-extensions/FixedHeader/js/dataTables.fixedHeader.min.js',
            '/static/components/vendor/datatables-extensions/JSZip/jszip.min.js',
            '/static/components/vendor/datatables-extensions/pdfmake/build/pdfmake.min.js',
            '/static/components/vendor/datatables-extensions/pdfmake/build/vfs_fonts.js',
            '/static/components/vendor/datatables-extensions/Responsive/css/responsive.dataTables.min.css',
            '/static/components/vendor/datatables-extensions/Responsive/js/dataTables.responsive.min.js',
            '/static/components/vendor/datatables-extensions/rowgroup/css/rowGroup.dataTables.min.css',
            '/static/components/vendor/datatables-extensions/rowgroup/js/dataTables.rowGroup.js',
            '/static/components/vendor/datatables/css/dataTables.dataTables.css',
            '/static/components/vendor/datatables/js/dataTables.min.js',
            '/static/components/vendor/jquery/jquery.min.js',
            '/static/components/vendor/popper/popper.min.js',
            '/static/components/vendor/typeahead/jquery.typeahead.min.css',
            '/static/components/vendor/typeahead/jquery.typeahead.min.js',
            '/static/components/vendor/typeahead/jquery.typeahead.min.js',
            '/static/favicon',
            '/static/header_logo',
            '/static/main.css',
        ]
    )
    def test_static(self, url):
        self.getPage(url)
        self.assertStatus(200)
