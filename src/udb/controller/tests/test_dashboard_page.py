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


from udb.controller import url_for
from udb.controller.tests import WebCase


class TestDashboardPage(WebCase):
    def test_dashboard(self):
        # Given the application is started
        # When making a query to index page
        self.getPage('/dashboard/')
        # Then an html page is returned
        self.assertInBody("Last activities")

    def test_dashboard_selenium(self):
        # Given a database with data
        self.add_records()
        with self.selenium(headless=False) as driver:
            # When making a query to audit log
            driver.get(url_for('dashboard'))
            driver.implicitly_wait(10)
            # Then the web page contains a table
            driver.find_element('css selector', 'table.table')
            # Then the web page is loaded without error.
            self.assertFalse(driver.get_log('browser'))
