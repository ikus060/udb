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


from io import StringIO

import requests

from udb.controller import url_for
from udb.controller.tests import WebCase
from udb.core.model import DnsRecord, DnsZone, Subnet, Vrf

SUBNET1 = """IPv6,IPv4,VRF,L3VNI,L2VNI,VLAN,TLD,Name,Description
2a07:6b40::/32 ,,infra,,,,,Infra,
2a07:6b40:0::/48,,client,14,,,bfh.info,all-anycast-infra,All: anycast Infrastructure
2a07:6b40:0::/48,,infra,10,,,bfh.info,all-anycast-infra,All: anycast Infrastructure
"""

DNSRECORD1 = """;; AXFR for bfh.ch.
bfh.ch.             	600	IN	SOA	ddns.bfh.info. bfh-linux-sysadmin.lists.bfh.science. 33317735 600 60 36000 3600
bfh.ch.             	600	IN	A	147.87.0.240
bfh.ch.             	600	IN	NS	node1.ns.bfh.info.
"""


class LoadPageTest(WebCase):
    def test_import_subnet(self):
        # Given an empty database
        # When importing subnet
        r = requests.post(
            url_for('load', ''),
            cookies={'session_id': self.session_id},
            data={'type_file': 'subnet'},
            files={'upload_file': ('subnet.csv', StringIO(SUBNET1))},
            proxies={'http': None},
        )
        self.assertEqual(200, r.status_code)
        self.assertIn('CSV File imported with success !', r.text)
        # Then subnet record get created
        self.assertEqual(3, Subnet.query.count())
        self.assertEqual(2, Vrf.query.count())

    def test_import_dnsrecord(self):
        # Given a database with a VRF and Subnet
        vrf = Vrf(name='default').add()
        zone = DnsZone(name='bfh.ch').add()
        Subnet(range='147.87.0.0/24', name='DMZ', vrf=vrf, dnszones=[zone]).add().commit()
        # When importing subnet
        r = requests.post(
            url_for('load', ''),
            cookies={'session_id': self.session_id},
            data={'type_file': 'dnsrecord'},
            files={'upload_file': ('bfh.ch', StringIO(DNSRECORD1))},
            proxies={'http': None},
        )
        self.assertEqual(200, r.status_code)
        self.assertIn('CSV File imported with success !', r.text)
        # Then subnet record get created
        self.assertEqual(3, DnsRecord.query.count())
