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


from udb.controller.tests import WebCase


class TestSearchPage(WebCase):
    def test_search(self):
        # Given a database with records
        self.add_records()
        # When making a query to index page
        self.getPage('/search/')
        # Then an html page is returned
        self.assertStatus(200)
        self.assertInBody('Search')
        self.assertInBody('Sorry, that filter combination has no result.')

    def test_search_with_query(self):
        # Given a database with records
        self.add_records()
        # When making a query to the index page
        self.getPage('/search/query.json?q=public')
        # Then results are displayed
        self.assertStatus(200)
        self.assertInBody('DMZ')
