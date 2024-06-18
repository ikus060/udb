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


from selenium.webdriver.common.keys import Keys

from udb.controller import url_for
from udb.controller.tests import WebCase
from udb.core.model import DnsRecord, DnsZone, Subnet, Vrf

from .test_common_page import CommonTest


class DnsZonePageTest(WebCase, CommonTest):

    base_url = 'dnszone'

    new_data = {'name': 'examples.com'}

    edit_data = {'name': 'this.is.a.new.value.com'}

    obj_cls = DnsZone

    def test_edit_invalid(self):
        # Given a database with a record
        obj = self.obj_cls(**self.new_data).add()
        obj.commit()
        # When trying to update it's name
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body={'name': 'invalid new name'})
        # Then edit page is displayed with an error message
        self.assertStatus(200)
        self.assertInBody('must be a valid domain name')

    def test_edit_with_subnet(self):
        # Given a database with a record
        vrf = Vrf(name='default').add()
        subnet = Subnet(range='192.168.0.1/24', vrf=vrf).add()
        obj = self.obj_cls(**{'name': 'examples.com', 'subnets': [subnet]}).add()
        obj.commit()
        # When editing the record
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        # Then subnets are select
        self.assertStatus(200)
        self.assertInBody('<option selected value="%s">' % subnet.id)

    def test_edit_add_subnet(self):
        # Given a database with a record
        vrf = Vrf(name='default').add()
        subnet = Subnet(range='192.168.0.1/24', vrf=vrf).add()
        obj = self.obj_cls(**{'name': 'examples.com', 'subnets': []}).add()
        obj.commit()
        # When editing the record
        self.getPage(url_for(self.base_url, obj.id, 'edit'), method='POST', body={'subnets': subnet.id})
        self.assertStatus(303)
        # Then subnets are select
        self.getPage(url_for(self.base_url, obj.id, 'edit'))
        self.assertStatus(200)
        self.assertInBody('<option selected value="%s">' % subnet.id)

    def test_edit_add_subnet_selenium(self):
        # Given a database with a record
        vrf = Vrf(name='default').add()
        slave = Subnet(range='192.168.1.0/24')
        subnet = Subnet(range='192.168.0.1/24', vrf=vrf, slave_subnets=[slave]).add()
        zone = DnsZone(name='examples.com').add()
        zone.commit()
        # When adding subnet using the side-by-side widget
        with self.selenium() as driver:
            # When getting web page.
            driver.get(url_for(self.base_url, zone.id, 'edit'))
            # Then the web page is loaded without error.
            self.assertFalse(driver.get_log('browser'))
            # Then the web page contains a save button
            save_btn = driver.find_element('id', 'save-changes')
            # Then the web page contains out subnet item
            subnet_item = driver.find_element('css selector', '[data-value="%s"]' % subnet.id)
            # When selecting the subnet item and saving
            subnet_item.click()
            save_btn.send_keys(Keys.ENTER)
            # Then the page get refresh
            driver.implicitly_wait(10)
            driver.find_element('xpath', "//*[contains(text(), 'Modified by')]")
            # Then the database get updated with changes.
            zone.expire()
            self.assertEqual(2, len(zone.subnets))
            self.assertIn(subnet, zone.subnets)
            self.assertIn(slave, zone.subnets)

    def test_edit_remove_subnet_selenium(self):
        # Given a database with a record
        vrf = Vrf(name='default').add()
        slave = Subnet(range='192.168.1.0/24')
        subnet = Subnet(range='192.168.0.1/24', vrf=vrf, slave_subnets=[slave]).add()
        zone = DnsZone(name='examples.com', subnets=[subnet]).add().commit()
        self.assertEqual(2, len(zone.subnets))

        # When adding subnet using the side-by-side widget
        with self.selenium() as driver:
            # When getting web page.
            driver.get(url_for(self.base_url, zone.id, 'edit'))
            # Then the web page is loaded without error.
            self.assertFalse(driver.get_log('browser'))
            # Then the web page contains a save button
            save_btn = driver.find_element('id', 'save-changes')
            # Then the web page contains out subnet item
            subnet_item = driver.find_element('css selector', '[data-value="%s"]' % subnet.id)
            # When selecting the subnet item and saving
            subnet_item.click()
            save_btn.send_keys(Keys.ENTER)
            # Then the page get refresh
            driver.implicitly_wait(10)
            driver.find_element('xpath', "//*[contains(text(), 'Modified by')]")
            # Then the database get updated with changes.
            zone.expire()
            self.assertEqual(0, len(zone.subnets))

    def test_zonefile(self):
        # Given a database with a record
        vrf = Vrf(name='default').add()
        subnet = Subnet(range='192.168.0.1/24', vrf=vrf).add()
        obj = self.obj_cls(**{'name': 'examples.com', 'subnets': [subnet]}).add().commit()
        DnsRecord(name='foo.examples.com', type='A', value='192.168.0.54', vrf=vrf).add().commit()
        # When downloading the zonefile
        self.getPage(url_for(self.base_url, obj.id, 'zonefile'))
        # Then zonefile is downloaded
        self.assertBody(";; Generated by UDB\nfoo.examples.com. 3600 IN A 192.168.0.54\n")

    def test_dnszone_duplicate(self):
        # Given an existing DNS Zone
        obj = DnsZone(name='examples.com').add().commit()
        # When trying to create a zone with the same name
        self.getPage(url_for(self.base_url, 'new'), method='POST', body={'name': 'examples.com'})
        # Then an error is returned
        self.assertStatus(200)
        self.assertInBody('A DNS Zone aready exist for this domain.')
        # Then a link to the original record is return.
        self.assertInBody(url_for(obj, 'edit'))
