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


import json
import os
import unittest
from urllib.parse import urlencode

import cherrypy
import cherrypy.test.helper

from udb.app import Root
from udb.config import parse_args
from udb.core.model import User

BaseClass = cherrypy.test.helper.CPWebCase
del BaseClass.test_gc


class WebCase(BaseClass):
    """
    Helper class for the test suite.
    """

    interactive = False  # Disable interactive test

    login = True  # Login by default.
    username = 'admin'
    password = 'admin'

    default_config = {}

    @classmethod
    def setup_class(cls):
        if cls is WebCase:
            raise unittest.SkipTest("%s is an abstract base class" % cls.__name__)
        super().setup_class()

    @classmethod
    def teardown_class(cls):
        super().teardown_class()

    @classmethod
    def setup_server(cls):
        # Get defaultconfig from test class
        default_config = getattr(cls, 'default_config', {})
        # Replace database url
        dburi = os.environ.get('TEST_DATABASE_URI', None)
        if dburi:
            default_config['database-uri'] = dburi

        cfg = parse_args(args=[], config_file_contents='\n'.join('%s=%s' % (k, v) for k, v in default_config.items()))
        app = Root(cfg)
        cherrypy.tree.mount(app)

    def setUp(self):
        super().setUp()
        cherrypy.tools.db.drop_all()
        cherrypy.tools.db.create_all()
        if self.login:
            self._login()

    def tearDown(self):
        cherrypy.tools.db.drop_all()
        super().tearDown()

    @property
    def app(self):
        """
        Return reference to application.
        """
        return cherrypy.tree.apps[''].root

    @property
    def session(self):
        return cherrypy.tools.db.get_session()

    @property
    def baseurl(self):
        return 'http://%s:%s' % (self.HOST, self.PORT)

    def getPage(self, url, headers=None, method="GET", body=None, protocol=None):
        if headers is None:
            headers = []
        # When body is a dict, send the data as form data.
        if isinstance(body, dict) and method in ['POST', 'PUT']:
            data = [(str(k).encode(encoding='latin1'), str(v).encode(encoding='utf-8')) for k, v in body.items()]
            body = urlencode(data)
        # Send back cookies if any
        if hasattr(self, 'cookies') and self.cookies:
            headers.extend(self.cookies)
        # CherryPy ~8.9.1 is not handling absolute URL properly and web browser
        # are usually not sending absolute URL either. So trim the base.
        base = 'http://%s:%s' % (self.HOST, self.PORT)
        if url.startswith(base):
            url = url[len(base) : :]
        super().getPage(url, headers, method, body, protocol)

    def getJson(self, *args, **kwargs):
        self.getPage(*args, **kwargs)
        self.assertStatus(200)
        return json.loads(self.body.decode('utf8'))

    def _login(self, username=username, password=password, redirect='/'):
        # Create new user
        User.create_default_admin(username, password)
        self.session.commit()
        # Authenticate
        self.getPage("/login/", method='POST', body={'username': username, 'password': password, 'redirect': redirect})
        self.assertStatus('303 See Other')
