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
from base64 import b64encode

from parameterized import parameterized

from udb.controller import url_for
from udb.controller.tests import WebCase
from udb.core.model import DnsZone, User


class RoleTest(WebCase):
    """
    Test role verification.
    """

    login = False

    authorization = [('Authorization', 'Basic %s' % b64encode(b'test-user:password').decode('ascii'))]

    def setUp(self):
        super().setUp()
        self.add_records()
        self.user = User.create(username='test-user', password='password', role='guest').add()
        self.user.commit()
        self.getPage("/login/", method='POST', body={'username': self.user, 'password': 'password', 'redirect': '/'})
        self.assertStatus('303 See Other')

    @parameterized.expand(
        [
            ({'url': '/deployment/'},),
            ({'url': '/deployment/1/view'},),
            ({'url': '/dhcprecord/'},),
            ({'url': '/dhcprecord/new'}, False),
            ({'url': '/dhcprecord/1/edit'},),
            ({'url': '/dhcprecord/1/edit', 'method': 'POST', 'body': {'notes': 'newvalue'}}, False),
            ({'url': '/dnsrecord/'},),
            ({'url': '/dnsrecord/new'}, False),
            ({'url': '/dnsrecord/1/edit'},),
            ({'url': '/dnsrecord/1/edit', 'method': 'POST', 'body': {'notes': 'newvalue'}}, False),
            ({'url': '/dnszone/'},),
            ({'url': '/dnszone/new'}, False, False),
            ({'url': '/dnszone/1/edit'},),
            ({'url': '/dnszone/1/edit', 'method': 'POST', 'body': {'notes': 'newvalue'}}, False),
            ({'url': '/environment/'},),
            ({'url': '/environment/new'}, False, False, False, False),
            ({'url': '/environment/1/edit'},),
            (
                {'url': '/environment/1/edit', 'method': 'POST', 'body': {'notes': 'newvalue'}},
                False,
                False,
                False,
                False,
            ),
            ({'url': '/mac/'},),
            ({'url': '/subnet/'},),
            ({'url': '/subnet/new'}, False, False, False),
            ({'url': '/subnet/1/edit'},),
            ({'url': '/subnet/1/edit', 'method': 'POST', 'body': {'notes': 'newvalue'}}, False),
            ({'url': '/user/'}, False, False, False, False),
            ({'url': '/user/new'}, False, False, False, False),
            ({'url': '/user/1/edit'}, False, False, False, False),
            ({'url': '/user/1/edit', 'method': 'POST', 'body': {'notes': 'newvalue'}}, False, False, False, False),
            ({'url': '/vrf/'},),
            ({'url': '/vrf/new'}, False),
            ({'url': '/vrf/1/edit'},),
            ({'url': '/vrf/1/edit', 'method': 'POST', 'body': {'notes': 'newvalue'}}, False),
            ({'url': '/search/'},),
        ],
        name_func=lambda func, num, p: func.__name__
        + parameterized.to_safe_name(p.args[0]['url'] + p.args[0].get('method', ''))
        + "_%s" % (num,),
    )
    def test_access(
        self,
        query,
        guest_access=True,
        user_access=True,
        dnszone_mgmt_access=True,
        subnet_mgmt_access=True,
        admin_access=True,
    ):
        # Test as guest
        self.getPage(**query)
        self.assertStatus(200 if guest_access else 403, 'wrong access for guest')

        # Test as user
        self.user.role = 'user'
        self.user.commit()
        self.getPage(**query)
        if query.get('method', None) == 'POST':
            self.assertStatus(303 if user_access else 403, 'wrong access for user')
        else:
            self.assertStatus(200 if user_access else 403, 'wrong access for user')

        # Test as user
        self.user.role = 'dnszone-mgmt'
        self.user.commit()
        self.getPage(**query)
        if query.get('method', None) == 'POST':
            self.assertStatus(303 if dnszone_mgmt_access else 403, 'wrong access for dnszone-mgmt')
        else:
            self.assertStatus(200 if dnszone_mgmt_access else 403, 'wrong access for dnszone-mgmt')

        # Test as user
        self.user.role = 'subnet-mgmt'
        self.user.commit()
        self.getPage(**query)
        if query.get('method', None) == 'POST':
            self.assertStatus(303 if subnet_mgmt_access else 403, 'wrong access for subnet-mgmt')
        else:
            self.assertStatus(200 if subnet_mgmt_access else 403, 'wrong access for subnet-mgmt')

        # Test as user
        self.user.role = 'admin'
        self.user.commit()
        self.getPage(**query)
        if query.get('method', None) == 'POST':
            self.assertStatus(303 if admin_access else 403, 'wrong access for admin')
        else:
            self.assertStatus(200 if admin_access else 403, 'wrong access for admin')

    def test_api_post_as_guest(self):
        # Given a valid payload
        payload = json.dumps({'name': 'newname.com'})
        # When sending a POST request to the API
        self.getPage(
            url_for('api', 'dnszone'),
            headers=[('Content-Type', 'application/json'), ('Content-Length', str(len(payload)))] + self.authorization,
            method='POST',
            body=payload,
        )
        # Then a 403 Forbidden is raised
        self.assertStatus(403)

    def test_api_put_as_guest(self):
        # Given a existing record
        obj = DnsZone(name='examples.com').add()
        obj.commit()
        # Given a valid payload
        payload = json.dumps({'name': 'newname.com'})
        # When sending a PUT request to the API
        self.getPage(
            url_for('api', 'dnszone', obj.id),
            headers=[('Content-Type', 'application/json'), ('Content-Length', str(len(payload)))] + self.authorization,
            method='PUT',
            body=payload,
        )
        # Then a 403 Forbidden is raised
        self.assertStatus(403)
