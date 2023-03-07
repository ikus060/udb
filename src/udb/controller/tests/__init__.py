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

import json
import os
import tempfile
import time
import unittest
from contextlib import contextmanager
from urllib.parse import urlencode

import cherrypy
import cherrypy.test.helper
from selenium import webdriver

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

    default_config = {'debug': True}

    @classmethod
    def setup_class(cls):
        if cls is WebCase:
            raise unittest.SkipTest("%s is an abstract base class" % cls.__name__)
        super().setup_class()

    @classmethod
    def teardown_class(cls):
        super().teardown_class()

    def wait_for_tasks(self):
        count = 0
        time.sleep(0.25)
        while count < 20 and len(cherrypy.scheduler.list_tasks()) or cherrypy.scheduler.is_job_running():
            time.sleep(0.5)

    @classmethod
    def setup_server(cls):
        # Get defaultconfig from test class
        default_config = getattr(cls, 'default_config', {})
        # Replace database url
        dburi = os.environ.get('TEST_DATABASE_URI', 'sqlite:///' + tempfile.gettempdir() + '/test_udb_data.db')
        default_config['database-uri'] = dburi
        if 'rate-limit' not in default_config:
            default_config['rate-limit'] = -1
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
        # Need to wait for task before deleting to avoid dead lock in postgresql.
        self.wait_for_tasks()
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
            data = []
            for k, v in body.items():
                if isinstance(v, list):
                    data.extend(
                        [
                            (
                                str(k).encode(encoding='latin1'),
                                str(item).encode(encoding='utf-8'),
                            )
                            for item in v
                        ]
                    )
                else:
                    data.append(
                        (
                            str(k).encode(encoding='latin1'),
                            str(v).encode(encoding='utf-8'),
                        )
                    )
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
        user = User.create_default_admin(username, password)
        if user:
            user.commit()
        # Authenticate
        self.getPage("/login/", method='POST', body={'username': username, 'password': password, 'redirect': redirect})
        self.assertStatus('303 See Other')

    @property
    def session_id(self):
        if hasattr(self, 'cookies') and self.cookies:
            for unused, value in self.cookies:
                for part in value.split(';'):
                    key, unused, value = part.partition('=')
                    if key == 'session_id':
                        return value

    @contextmanager
    def selenium(self):
        """
        Decorator to load selenium for a test.
        """
        # Skip selenium test is display is not available.
        if not os.environ.get('DISPLAY', False):
            raise unittest.SkipTest("selenium require a display")
        # Start selenium driver
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        if os.geteuid() == 0:
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Chrome(options=options)
        # If logged in, reuse the same session id.
        try:
            if self.session_id:
                driver.get('http://%s:%s/login/' % (self.HOST, self.PORT))
                driver.add_cookie({"name": "session_id", "value": self.session_id})
            yield driver
        finally:
            # Code to release resource, e.g.:
            driver.close()
