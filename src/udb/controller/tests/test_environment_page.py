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
from udb.core.model import Deployment, DhcpRecord, Environment, Message, Subnet, SubnetRange, Vrf

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
        Subnet(
            subnet_ranges=[
                SubnetRange(
                    '192.168.45.0/24',
                    dhcp=True,
                    dhcp_start_ip='192.168.45.1',
                    dhcp_end_ip='192.168.45.254',
                )
            ],
            vrf=vrf,
        ).add().commit()
        # Given a database with DHCP Record change
        DhcpRecord(ip='192.168.45.67', mac='E5:D3:56:7B:22:A3', vrf=vrf).add().commit()

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
        # When a deployment is triggered without a last_changes value
        self.getPage(url_for(self.base_url, obj.id, 'deploy'), method='POST')
        # Then user is redirect to environment page
        self.assertStatus(303)
        self.assertHeaderItemValue("Location", self.baseurl + "/environment/%s/edit" % obj.id)
        # Then an error is displayed
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        self.assertStatus(200)
        self.assertInBody('last_change: This field is required.')

    def test_deploy_with_obsolete_last_change(self):
        # Given a new environment
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When a deployment is triggered with an obsolete last_change value
        self.getPage(url_for(self.base_url, obj.id, 'deploy'), method='POST', body={'last_change': '1'})
        # Then user is redirect to environment page
        self.assertStatus(303)
        self.assertHeaderItemValue("Location", self.baseurl + "/environment/%s/edit" % obj.id)
        # Then an error is displayed
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        self.assertStatus(200)
        self.assertInBody(
            'A recent changes was submited preventing the deployment. Please, review the latest changes befor deploying again.'
        )

    def test_deploy_without_changes(self):
        # Given a new environment that was deployed
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        last_change = Message.query.order_by(Message.id.desc()).first().id
        self.getPage(url_for(self.base_url, obj.id, 'deploy'), method='POST', body={'last_change': last_change})
        self.assertStatus(303)
        self.assertEqual(Deployment.query.count(), 1)
        # When deploying again without changes.
        self.getPage(url_for(self.base_url, obj.id, 'deploy'), method='POST', body={'last_change': -1})
        self.assertStatus(303)
        deployment = Deployment.query.order_by(Deployment.id.desc()).first()
        self.assertHeaderItemValue("Location", self.baseurl + "/deployment/%s/view" % deployment.id)
        # Then deployment is success
        self.wait_for_tasks()
        deployment.expire()
        self.assertEqual(deployment.state, Deployment.STATE_SUCCESS)

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
        self.assertIsNotNone(deployment.owner)
        self.assertHeaderItemValue("Location", self.baseurl + "/deployment/%s/view" % deployment.id)
        # When querying the deployment page
        self.getPage(self.baseurl + "/deployment/%s/view" % deployment.id)
        # Then the deployment is starting or running
        self.assertStatus(200)
        self.assertInBody("Deployment scheduled...")
        # Then deployment is success
        self.wait_for_tasks()
        deployment.expire()
        self.assertEqual(deployment.state, Deployment.STATE_SUCCESS)

    def test_get_data_json_with_changes(self):
        # Given an environment
        Environment(name='subnet_env', model_name='subnet').add().commit()
        Environment(name='dhcp_env', model_name='dhcprecord').add().commit()
        # When listing the data
        data = self.getJson(url_for(self.base_url, 'data.json'))
        # Then the change_count is defined
        self.assertEqual(
            data['data'],
            [
                [1, 'enabled', 'subnet_env', 'subnet', 2, '', '/environment/1/edit'],
                [2, 'enabled', 'dhcp_env', 'dhcprecord', 2, '', '/environment/2/edit'],
            ],
        )
