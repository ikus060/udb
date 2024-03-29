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

import fnmatch
import json
import os
import shutil
import tempfile
import time
import unittest
from contextlib import contextmanager
from urllib.parse import urlencode

import cherrypy
import cherrypy.test.helper
import html5lib
from selenium import webdriver
from sqlalchemy.orm import close_all_sessions

from udb.app import UdbApplication
from udb.config import parse_args
from udb.core.model import Deployment, DhcpRecord, DnsRecord, DnsZone, Environment, Message, Subnet, User, Vrf

BaseClass = cherrypy.test.helper.CPWebCase
del BaseClass.test_gc


class MATCH(object):
    "A helper object that compares equal using wildcard."

    def __init__(self, pattern):
        self.pattern = pattern

    def __eq__(self, other):
        return fnmatch.fnmatch(other, self.pattern)

    def __ne__(self, other):
        return not fnmatch.fnmatch(other, self.pattern)

    def __repr__(self):
        return '<MATCH %s>' % self.pattern


class WebCase(BaseClass):
    """
    Helper class for the test suite.
    """

    interactive = False  # Disable interactive test

    login = True  # Login by default.
    username = 'admin'
    password = 'admin'

    default_config = {'debug': False}

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
        time.sleep(0.02)
        while count < 20 and len(cherrypy.scheduler.list_tasks()) or cherrypy.scheduler.is_job_running():
            time.sleep(0.02)
            count += 1
        self.assertFalse(cherrypy.scheduler.list_tasks())
        self.assertFalse(cherrypy.scheduler.is_job_running())

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
        app = UdbApplication(cfg)
        cherrypy.tree.mount(app)

    def setUp(self):
        super().setUp()
        # Close all session
        close_all_sessions()
        # Drop previous tables
        cherrypy.tools.db.drop_all()
        # Create new tables.
        cherrypy.tools.db.create_all()
        if self.login:
            self._login()

    def tearDown(self):
        # Need to wait for task before deleting to avoid dead lock in postgresql.
        self.wait_for_tasks()
        # Close all session
        close_all_sessions()
        # Drop tables
        cherrypy.tools.db.drop_all()
        # Delete selenium download
        if getattr(self, '_selenium_download_dir', False):
            shutil.rmtree(self._selenium_download_dir)
            self._selenium_download_dir = None
        super().tearDown()

    def add_records(self):
        """
        Generate a preset of data for testing.
        """
        self.user = User(username='test')
        self.vrf = Vrf(name='(default)')
        self.subnet = Subnet(
            range='147.87.250.0/24',
            dhcp=True,
            dhcp_start_ip='147.87.250.100',
            dhcp_end_ip='147.87.250.200',
            name='DMZ',
            vrf=self.vrf,
            notes='public',
            owner=self.user,
        ).add()
        self.subnet.add_message(Message(body='Message on subnet', author=self.user))
        Subnet(range='147.87.0.0/16', name='its-main-4', vrf=self.vrf, notes='main', owner=self.user).add()
        Subnet(
            range='2002::1234:abcd:ffff:c0a8:101/64',
            name='its-main-6',
            vrf=self.vrf,
            notes='main',
            owner=self.user,
        ).add()
        Subnet(range='147.87.208.0/24', name='ARZ', vrf=self.vrf, notes='BE.net', owner=self.user).add()
        self.zone = DnsZone(name='bfh.ch', notes='DMZ Zone', subnets=[self.subnet], owner=self.user).add()
        self.zone.add_message(Message(body='Here is a message', author=self.user))
        self.zone.flush()
        DnsZone(name='bfh.science', notes='This is a note', owner=self.user).add()
        DnsZone(name='bfh.info', notes='This is a note', owner=self.user).add()
        DhcpRecord(ip='147.87.250.1', mac='00:ba:d5:a2:34:56', notes='webserver bla bla bla', owner=self.user).add()
        self.dnsrecord = DnsRecord(
            name='foo.bfh.ch', type='A', value='147.87.250.3', owner=self.user, vrf=self.vrf
        ).add()
        self.dnsrecord.add_message(Message(body='This is a message', author=self.user))
        DnsRecord(name='bar.bfh.ch', type='A', value='147.87.250.1', owner=self.user, vrf=self.vrf).add()
        DnsRecord(name='bar.bfh.ch', type='CNAME', value='www.bar.bfh.ch', owner=self.user, vrf=self.vrf).add()
        DnsRecord(name='baz.bfh.ch', type='A', value='147.87.250.2', owner=self.user, vrf=self.vrf).add()
        env = Environment(name='test-env', script='echo FOO', model_name='dhcprecord').add().commit()
        Deployment(
            environment_id=env.id,
            owner=User.query.first(),
            change_count=1,
            start_id=0,
            end_id=Message.query.order_by(Message.id.desc()).first().id,
        ).add().commit()

    def assertValidHTML(self, msg=None):
        """
        Verify if the current body is compliant HTML.
        """
        try:
            parser = html5lib.HTMLParser(strict=True)
            parser.parse(self.body)
        except html5lib.html5parser.ParseError as e:
            self.assertHeader
            row, col_unused = parser.errors[0][0]
            line = self.body.splitlines()[row - 1].decode('utf8', errors='replace')
            msg = msg or ('URL %s contains invalid HTML: %s on line %s: %s' % (self.url, e, row, line))
            self.fail(msg)

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
        self.getPage("/logout", method="POST")
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
    def selenium(self, headless=True):
        """
        Decorator to load selenium for a test.
        """
        # Skip selenium test is display is not available.
        if not os.environ.get('DISPLAY', False):
            raise unittest.SkipTest("selenium require a display")
        # Start selenium driver
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1280,800')
        if os.geteuid() == 0:
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
        # for selenium >=4.11, explicitly define location of chronium driver.
        if hasattr(webdriver, 'ChromeService'):
            chrome_service_cls = getattr(webdriver, 'ChromeService')
            service = chrome_service_cls(executable_path=shutil.which('chromedriver'))
        else:
            service = None
        driver = webdriver.Chrome(options=options, service=service)
        try:
            # If logged in, reuse the same session id.
            if self.session_id:
                driver.get('http://%s:%s/login/' % (self.HOST, self.PORT))
                driver.add_cookie({"name": "session_id", "value": self.session_id})
            # Configure download folder
            download = os.path.join(os.path.expanduser('~'), 'Downloads')
            os.makedirs(download, exist_ok=True)
            self._selenium_download_dir = tempfile.mkdtemp(dir=download, prefix='udb-selenium-download-')
            driver.execute_cdp_cmd(
                'Page.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': self._selenium_download_dir}
            )
            yield driver
        finally:
            # Code to release resource, e.g.:
            driver.close()
            driver = None

    def assertSeleniumDownload(self, timeout=10):
        """
        Check number of file in download folder
        """
        # Wait until file get downloaded.
        # Make sure to ignore '.crdownload'
        for unused in range(1, timeout):
            files = [f for f in os.listdir(self._selenium_download_dir) if not f.endswith('.crdownload')]
            if len(files) > 0:
                break
            time.sleep(1)
        files = os.listdir(self._selenium_download_dir)
        self.assertTrue(files)
        return files[0]
