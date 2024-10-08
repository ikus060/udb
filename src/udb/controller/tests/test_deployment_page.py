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

from base64 import b64encode
from unittest.mock import ANY

from udb.controller import url_for
from udb.controller.tests import WebCase
from udb.core.model import Deployment, DhcpRecord, DnsRecord, DnsZone, Environment, Message, Subnet, User, Vrf


class DeploymentPageTest(WebCase):

    base_url = 'deployment'

    obj_cls = Deployment

    new_data = {}

    authorization = [('Authorization', 'Basic %s' % b64encode(b'admin:admin').decode('ascii'))]

    def setUp(self):
        super().setUp()
        # Generate a changes
        vrf = Vrf(name='default')
        Subnet(
            range='192.168.45.0/24',
            dhcp=True,
            dhcp_start_ip='192.168.45.1',
            dhcp_end_ip='192.168.45.100',
            vrf=vrf,
        ).add().commit()
        DhcpRecord(ip='192.168.45.67', mac='E5:D3:56:7B:22:A3', vrf=vrf).add().commit()
        # Create a new environment
        self.environment = Environment(name='test-env', script='echo FOO', model_name='dhcprecord').add().commit()
        self.new_data = {
            'environment_id': self.environment.id,
            'owner': User.query.first(),
            'change_count': 1,
            'start_id': 0,
            'end_id': Message.query.order_by(Message.id.desc()).first().id,
        }

    def test_get_list_page_empty(self):
        # Given a database without record
        # When making a query to list page
        self.getPage(url_for(self.base_url, ''))
        # Then an html page is returned with a table
        self.assertStatus(200)
        self.assertInBody('<table')

    def test_get_view_page(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When querying the view page
        self.getPage(url_for(self.base_url, obj.id, 'view'))
        # Then return not found
        self.assertStatus(200)
        self.assertInBody('Deployment #%s' % obj.id)

    def test_get_view_page_selenium(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        with self.selenium() as driver:
            # When querying the view page
            driver.get(url_for(self.base_url, obj.id, 'view'))
            driver.implicitly_wait(10)
            # Then the web page contains log
            driver.find_element('css selector', 'code')
            # Then the web page is loaded without error.
            self.assertFalse(driver.get_log('browser'))

    def test_get_changes_page(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When querying the changes page
        self.getPage(url_for(self.base_url, obj.id, 'changes'))
        # Then return not found
        self.assertStatus(200)
        self.assertInBody('Deployment #%s' % obj.id)

    def test_get_changes_page_selenium(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        with self.selenium() as driver:
            # When querying the changes page
            driver.get(url_for(self.base_url, obj.id, 'changes'))
            driver.implicitly_wait(10)
            # Then the web page contains a table
            driver.find_element('css selector', 'table.table')
            # Then the web page is loaded without error.
            self.assertFalse(driver.get_log('browser'))

    def test_get_deployments_json(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When querying changes.json
        data = self.getJson(url_for(self.base_url, 'deployments.json'))
        # Then return list of changes
        self.assertStatus(200)
        self.assertHeaderItemValue('Content-Type', 'application/json')
        self.assertEqual(
            data['data'],
            [
                [
                    1,
                    0,
                    'test-env',
                    ANY,
                    1,
                    'admin',
                    'http://127.0.0.1:54583/deployment/1/view',
                ]
            ],
        )

    def test_get_deployment_changes_json(self):
        # Given a new deployment
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When querying changes.json
        data = self.getJson(url_for(self.base_url, obj.id, 'changes.json'))
        # Then return dhcprecord and environment change.
        self.assertStatus(200)
        self.assertHeaderItemValue('Content-Type', 'application/json')
        self.assertEqual(
            sorted(data['data']),
            [
                [
                    1,
                    '192.168.45.67 (E5:D3:56:7B:22:A3)',
                    'dhcprecord',
                    'System',
                    ANY,
                    'new',
                    '',
                    {
                        'vrf': [None, 'default'],
                        'ip': [None, '192.168.45.67'],
                        'mac': [None, 'E5:D3:56:7B:22:A3'],
                        'subnet_estatus': [None, 2],
                        'subnet_range': [None, '192.168.45.0/24'],
                    },
                    '/dhcprecord/1/edit',
                ],
                [
                    1,
                    'test-env',
                    'environment',
                    'System',
                    ANY,
                    'new',
                    '',
                    {'name': [None, 'test-env'], 'script': [None, 'echo FOO'], 'model_name': [None, 'dhcprecord']},
                    '/environment/1/edit',
                ],
            ],
        )

    def test_get_deployment_api_data_json_without_authorization(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When querying the api/data.json
        self.getPage(url_for('api', self.base_url, obj.id, 'data.json'))
        # Then authorization error is returned
        self.assertStatus(401)

    def test_get_deployment_api_data_json_with_deployment_token(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When querying the api/data.json
        username = 'admin'
        password = obj.token
        auth = ('%s:%s' % (username, password)).encode('ascii')
        self.getPage(
            url_for('api', self.base_url, obj.id, 'data.json'),
            headers=[('Authorization', 'Basic %s' % b64encode(auth).decode('ascii'))],
        )
        # Then authorization error is returned
        self.assertStatus(200)

    def test_get_deployment_api_data_json(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When querying the api/data.json
        data = self.getJson(url_for('api', self.base_url, obj.id, 'data.json'), headers=self.authorization)
        # Then data is empty because deployment was not schedule.
        self.assertStatus(200)
        self.assertHeaderItemValue('Content-Type', 'application/json')
        self.assertEqual(1, len(data['dhcprecord']))

    def test_get_deployment_api_zonefile(self):
        # Given a datbase with a DnsRecord
        vrf = Vrf(name='test')
        builtin_zones = DnsZone.query.all()
        zone1 = DnsZone(name='test.ca').add()
        zone2 = DnsZone(name='example.com').add()
        Subnet(range='192.0.2.0/24', dnszones=[zone1, zone2, *builtin_zones], vrf=vrf).add().commit()
        DnsRecord(name='test.ca', type='A', value='192.0.2.45', vrf=vrf).add().commit()
        DnsRecord(name='example.com', type='A', value='192.0.2.23', vrf=vrf).add().commit()
        DnsRecord(name='23.2.0.192.in-addr.arpa', type='PTR', value='example.com', vrf=vrf).add().commit()
        DnsRecord(name='*.example.com', type='CNAME', value='bar.example.com', vrf=vrf).add().commit()
        DnsRecord(name='_acme-challenge.example.com', type='CNAME', value='foo.example.com', vrf=vrf).add().commit()
        # Given a new deployment
        env = Environment(name='test-env', script='echo FOO', model_name='dnsrecord').add().commit()
        deploy = Deployment(
            environment_id=env.id,
            owner=User.query.first(),
            change_count=1,
            start_id=0,
            end_id=Message.query.order_by(Message.id.desc()).first().id,
        )
        deploy.add().commit()
        # When querying the /api/deployment/46/zonefile?name=bfh.ch
        self.getPage(
            url_for('api', self.base_url, deploy.id, 'zonefile', name='example.com'), headers=self.authorization
        )
        # The zone file contains sorted DNS recrod for our zone
        self.assertStatus(200)
        self.assertHeaderItemValue('Content-Type', 'text/plain;charset=utf-8')
        self.assertBody(
            ';; Generated by UDB\nexample.com. 3600 IN A 192.0.2.23\n23.2.0.192.in-addr.arpa. 3600 IN PTR example.com\n_acme-challenge.example.com. 3600 IN CNAME foo.example.com.\n*.example.com. 3600 IN CNAME bar.example.com.\n'
        )

    def test_get_deployment_output_json(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When querying the output.json
        data = self.getJson(url_for(self.base_url, obj.id, 'output.json'))
        # Then data is empty because deployment was not schedule.
        self.assertStatus(200)
        self.assertHeaderItemValue('Content-Type', 'application/json')
        self.assertEqual(data, {'state': Deployment.STATE_STARTING, 'output': ''})

    def test_get_deployment_scheduled_output_json(self):
        # Given a database with a scheduled deployment.
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        obj.schedule_task(base_url=url_for())
        self.wait_for_tasks()
        # When querying the output.json
        data = self.getJson(url_for(self.base_url, obj.id, 'output.json'))
        # Then data is empty because deployment was not schedule.
        self.assertStatus(200)
        self.assertHeaderItemValue('Content-Type', 'application/json')
        self.assertEqual(data, {"state": Deployment.STATE_SUCCESS, "output": "FOO\n\nSUCCESS"})

    def test_get_edit_page_not_found(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When querying the edit page
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        # Then redirect to index page
        self.assertStatus(301)
        # When querying the edit page
        self.getPage(url_for(self.base_url, obj.id, 'edit', ''))
        # Then return not found
        self.assertStatus(404)

    def test_get_new_page_not_found(self):
        # Given an empty database
        # When querying the new page
        self.getPage(url_for(self.base_url, 'new'))
        # Then redirect to index page
        self.assertStatus(301)
        # When querying the new page
        self.getPage(url_for(self.base_url, 'new', ''))
        # Then return not found
        self.assertStatus(404)

    def test_get_changes_json_not_found(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When querying changes.json without a deployment id
        self.getPage(url_for(self.base_url, 'changes.json'))
        # Then return not found
        self.assertStatus(404)
