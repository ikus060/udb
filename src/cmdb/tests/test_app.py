
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

import cherrypy.test.helper

from cmdb.app import Root
from cmdb.config import parse_args


class TestApp(cherrypy.test.helper.CPWebCase):

    @classmethod
    def setup_server(cls):
        cfg = parse_args([])
        app = Root(cfg)
        cherrypy.tree.mount(app)

    def test_index(self):
        # Given the application is started
        # When making a query to index page
        self.getPage('/')
        # Then an html page is returned
        self.assertStatus(200)
        self.assertInBody('<body>')
