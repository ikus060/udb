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
from udb.core.model import DnsZone, Subnet, Vrf

from .test_network_page import CommonTest


class DnsZoneTest(WebCase, CommonTest):

    base_url = 'dnszone'

    new_data = {'name': 'examples.com'}

    edit_data = {'name': 'this.is.a.new.value.com'}

    obj_cls = DnsZone

    def test_edit_invalid(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        # When trying to update it's name
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body={'name': 'invalid new name'})
        self.session.commit()
        # Then edit page is displayed with an error message
        self.assertStatus(200)
        self.assertInBody('expected a valid FQDN')

    def test_edit_with_subnet(self):
        # Given a database with a record
        vrf = Vrf(name='default')
        subnet = Subnet(**{'ranges': ['192.168.0.1/24'], 'vrf': vrf}).add()
        obj = self.obj_cls(**{'name': 'examples.com', 'subnets': [subnet]}).add()
        # When editing the record
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        # Then subnets are select
        self.assertStatus(200)
        self.assertInBody(
            '<select name="subnets"\n            id="subnets"\n            class="form-control"\n            size="8"\n            multiple="multiple">\n      \n        \n          <option value="%s">'
            % subnet.id
        )

    def test_edit_add_subnet(self):
        # Given a database with a record
        vrf = Vrf(name='default')
        subnet = Subnet(**{'ranges': ['192.168.0.1/24'], 'vrf': vrf}).add()
        obj = self.obj_cls(**{'name': 'examples.com', 'subnets': []}).add()
        # When editing the record
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body={'subnets': subnet.id})
        self.assertStatus(303)
        # Then subnets are select
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        self.assertStatus(200)
        self.assertInBody(
            '<select name="subnets"\n            id="subnets"\n            class="form-control"\n            size="8"\n            multiple="multiple">\n      \n        \n          <option value="%s">'
            % subnet.id
        )
