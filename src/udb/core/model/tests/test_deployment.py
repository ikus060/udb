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

from unittest import mock

from sqlalchemy import func, select

from udb.controller.tests import WebCase
from udb.core.model import DhcpRecord, DnsRecord, DnsZone, Environment, Message, Subnet, SubnetRange, User, Vrf


class DeploymentTest(WebCase):
    def test_changes_subnet(self):
        # Given a database with a environment
        subnet_env = Environment(name='subnet_env', model_name='subnet').add()
        # Given a database with changes
        vrf = Vrf(name='default').add().flush()
        Subnet(name='LAN', subnet_ranges=[SubnetRange('192.168.14.0/24')], vrf=vrf).add().flush()
        DhcpRecord(ip='192.168.14.10', mac='5e:4b:85:7b:b4:2b', vrf=vrf).add().commit()
        # When creating a deployment
        user = User.query.first()
        deployment = subnet_env.create_deployment(user).add().commit()
        # Then it contains our changes.
        self.assertEqual(2, len(deployment.changes))

    def test_changes_dnsrecord(self):
        # Given a database with a environment
        dnsrecord_env = Environment(name='dnsrecord_env', model_name='dnsrecord').add()
        # Given a database with changes
        vrf = Vrf(name='default').add().flush()
        zone = DnsZone(name='example.com')
        Subnet(name='LAN', subnet_ranges=[SubnetRange('192.168.14.0/24')], vrf=vrf, dnszones=[zone]).add().flush()
        DnsRecord(name='example.com', type='A', value='192.168.14.15', vrf=vrf).add().commit()
        # When creating a deployment
        user = User.query.first()
        deployment = dnsrecord_env.create_deployment(user).add().commit()
        # Then it contains our changes.
        self.assertEqual(len(deployment.changes), 2)
        self.assertEqual(
            deployment.changes[0].changes,
            {'name': [None, 'dnsrecord_env'], 'model_name': [None, 'dnsrecord']},
        )
        self.assertEqual(
            deployment.changes[1].changes,
            {
                'name': [None, 'example.com'],
                'type': [None, 'A'],
                'value': [None, '192.168.14.15'],
                'vrf': [None, 'default'],
            },
        )

    def test_changes_dhcprecord(self):
        # Given a database with a environment
        dhcprecord_env = Environment(name='dhcprecord_env', model_name='dhcprecord').add()
        # Given a database with changes
        vrf = Vrf(name='default').add().flush()
        zone = DnsZone(name='example.com')
        Subnet(name='LAN', subnet_ranges=[SubnetRange('192.168.14.0/24')], vrf=vrf, dnszones=[zone]).add().flush()
        DhcpRecord(ip='192.168.14.10', mac='5e:4b:85:7b:b4:2b', vrf=vrf).add().commit()
        # When creating a deployment
        user = User.query.first()
        deployment = dhcprecord_env.create_deployment(user).add().commit()
        # Then it contains our changes.
        self.assertEqual(len(deployment.changes), 2)
        self.assertEqual(
            deployment.changes[0].changes,
            {'name': [None, 'dhcprecord_env'], 'model_name': [None, 'dhcprecord']},
        )
        self.assertEqual(
            deployment.changes[1].changes,
            {'ip': [None, '192.168.14.10'], 'mac': [None, '5e:4b:85:7b:b4:2b'], 'vrf': [None, 'default']},
        )


class EnvironmentTest(WebCase):
    def test_pending_changes(self):
        # Given a database with a environment
        subnet_env = Environment(name='subnet_env', model_name='subnet').add()
        dhcp_env = Environment(name='dhcp_env', model_name='dhcprecord').add().commit()
        # Given a database with changes
        vrf = Vrf(name='default').add().flush()
        Subnet(name='LAN', subnet_ranges=[SubnetRange('192.168.14.0/24')], vrf=vrf).add().flush()
        DhcpRecord(ip='192.168.14.10', mac='5e:4b:85:7b:b4:2b', vrf=vrf).add().commit()
        # When querying the pending changes
        # Then it return the changes
        self.assertEqual(2, len(subnet_env.pending_changes))
        self.assertEqual(2, len(dhcp_env.pending_changes))
        # When using select state
        # Then it return the count
        q = (
            select(Environment.name, func.count(Message.id))
            .outerjoin(Environment.pending_changes)
            .group_by(Environment.id)
        )
        environments = Environment.session.execute(q).all()
        self.assertIn(('subnet_env', 2), environments)
        self.assertIn(('dhcp_env', 2), environments)
        # Use min, max,count
        row = (
            Environment.query.with_entities(func.min(Message.id), func.max(Message.id), func.count(Message.id))
            .join(Environment.pending_changes)
            .filter(Environment.id == subnet_env.id)
            .first()
        )
        self.assertEqual((mock.ANY, mock.ANY, 2), row)
