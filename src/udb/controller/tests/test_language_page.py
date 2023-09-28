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


class LanguageTest(WebCase):
    def test_en(self):
        # Given the application is started
        # When making a query to index page
        data = self.getJson('/language/en')
        # Then an html page is returned
        self.assertEqual(data['zeroRecords'], 'List is empty')

    def test_fr(self):
        # Given the application is started
        # When getting the language file in french
        data = self.getJson('/language/fr')
        # Then a json is return with some data
        self.assertEqual(data['zeroRecords'], 'La liste est vide')
