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
from udb.core.model import Deployment, DhcpRecord, Environment, Message, Subnet, Vrf

from .test_common_page import CommonTest


class EnvironmentPageTest(WebCase, CommonTest):

    base_url = 'environment'

    obj_cls = Environment

    new_data = {'name': 'test-env', 'script': 'echo FOO', 'model_name': 'dhcprecord'}

    edit_data = {'script': 'echo BAR'}

    has_follow = False

    def setUp(self):
        super().setUp()
        # Generate a changes
        vrf = Vrf(name='default')
        Subnet(ranges=['192.168.45.0/24'], vrf=vrf, dhcp=True).add().commit()
        # Given a database with DHCP Record change
        DhcpRecord(ip='192.168.45.67', mac='E5:D3:56:7B:22:A3').add().commit()

    def test_follow(self):
        "Skip this test"
        pass

    def test_follow_get(self):
        "Skip this test"
        pass

    def test_unfollow(self):
        "Skip this test"
        pass

    def test_unfollow_get(self):
        "Skip this test"
        pass

    def test_deploy_wrong_method(self):
        # Given a new environment
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When a deployment is triggered
        self.getPage(url_for(self.base_url, obj.id, 'deploy'))
        # Then a 405 wrong method is raised
        self.assertStatus(405)

    def test_deploy_without_last_change(self):
        # Given a new environment
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When a deployment is triggered
        self.getPage(url_for(self.base_url, obj.id, 'deploy'), method='POST')
        # Then user is redirect to environment page
        self.assertStatus(303)
        self.assertHeaderItemValue("Location", self.baseurl + "/environment/%s/edit" % obj.id)

    def test_deploy(self):
        # Given a new environment
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        last_change = Message.query.order_by(Message.id.desc()).first().id
        # When a deployment is triggered with a valid last_change
        self.getPage(url_for(self.base_url, obj.id, 'deploy'), method='POST', body={'last_change': last_change})
        # Then user is redirect to deployment page
        self.assertStatus(303)
        deployment = Deployment.query.order_by(Deployment.id.desc()).first()
        self.assertHeaderItemValue("Location", self.baseurl + "/deployment/%s/view" % deployment.id)
        # When querying the deployment page
        self.getPage(self.baseurl + "/deployment/%s/view" % deployment.id)
        # Then the deployment is starting or running
        self.assertStatus(200)
        self.assertInBody("Deployment scheduled...")
