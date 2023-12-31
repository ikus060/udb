# -*- coding: utf-8 -*-
# udb, A web interface to rdiff-backup repositories
# Copyright (C) 2012-2021 udb contributors
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

import re
from collections import OrderedDict

from udb.controller.tests import WebCase


class CheckLinkTest(WebCase):

    login = True

    start_url = [
        "/dashboard/",
        "/vrf/1/edit",
        "/subnet/1/edit",
        "/ip/1/edit",
        "/dnszone/1/edit",
        "/dnsrecord/1/edit",
        "/dhcprecord/1/edit",
        "/mac/1/edit",
        "/environment/1/edit",
        "/deployment/1/view",
        "/user/1/edit",
        "/search/?q=test",
    ]

    ignore_url = [
        '.*/logout',
        '.*\\.js',
        '.*\\.svg',
        'https://gitlab.com/ikus-soft/udb',
    ]

    def setUp(self):
        super().setUp()
        self.add_records()

    def test_links(self):
        done = set(['#'])
        todo = OrderedDict()
        for url in self.start_url:
            todo[url] = 'start'
        # Store the original cookie since it get replace during execution.
        self.assertIsNotNone(self.cookies)
        cookies = self.cookies
        while todo:
            page, ref = todo.popitem(last=False)
            # Query page
            self.cookies = cookies
            self.getPage(page)
            # Check status
            if self.status_code in [301, 303]:
                newpage = self.assertHeader('Location')
                todo[newpage] = page
            else:
                self.assertStatus('200 OK', "can't access page [%s] referenced by [%s]" % (page, ref))

                # Check if valid HTML
                if dict(self.headers).get('Content-Type').startswith('text/html'):
                    self.assertValidHTML()

            done.add(page)

            # Collect all link in the page.
            for unused, newpage in re.findall("[\\s\\t](href|src)=\"([^\"]+)\"", self.body.decode('utf8', 'replace')):
                newpage = newpage.replace("&amp;", "&")
                if newpage.startswith("?"):
                    newpage = re.sub("\\?.*", "", page) + newpage
                if newpage not in done and not any(re.match(i, newpage) for i in self.ignore_url):
                    todo[newpage] = page
