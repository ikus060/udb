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


from datetime import datetime, timezone

import cherrypy

from udb.controller.tests import WebCase
from udb.tools import i18n


class TestI18nWebCase(WebCase):
    login = False

    def test_language_with_unknown(self):
        #  Query the page without login-in
        self.getPage("/login/", headers=[("Accept-Language", "it")])
        self.assertStatus('200 OK')
        self.assertHeaderItemValue("Content-Language", "en")
        self.assertInBody("Remember me")

    def test_language_en(self):
        self.getPage("/login/", headers=[("Accept-Language", "en-US,en;q=0.8")])
        self.assertStatus('200 OK')
        self.assertHeaderItemValue("Content-Language", "en")
        self.assertInBody("Remember me")

    def test_language_en_fr(self):
        self.getPage("/login/", headers=[("Accept-Language", "en-US,en;q=0.8,fr-CA;q=0.8")])
        self.assertStatus('200 OK')
        self.assertHeaderItemValue("Content-Language", "en")
        self.assertInBody("Remember me")

    def test_language_fr(self):
        self.getPage("/login/")
        self.assertInBody("Remember me")
        self.getPage("/login/", headers=[("Accept-Language", "fr-CA;q=0.8,fr;q=0.6")])
        self.assertStatus('200 OK')
        self.assertHeaderItemValue("Content-Language", "fr")
        self.assertInBody("Se souvenir de moi")

    def test_with_preferred_lang(self):
        # Given a default lang 'en'
        date = datetime.utcfromtimestamp(1680111611).replace(tzinfo=timezone.utc)
        self.assertEqual("Remember me", i18n.ugettext("Remember me"))
        self.assertIn('March', i18n.format_datetime(date, format='long'))
        # When using preferred_lang with french
        with i18n.preferred_lang('fr'):
            # Then french translation is used
            self.assertEqual('Se souvenir de moi', i18n.ugettext("Remember me"))
            # Then date time formating used french locale
            self.assertIn('mars', i18n.format_datetime(date, format='long'))
        # Then outside the block, settings goes back to english
        self.assertEqual("Remember me", i18n.ugettext("Remember me"))
        self.assertIn('March', i18n.format_datetime(date, format='long'))

    def test_list_available_locales(self):
        # Given a list of available language.
        # When listing availabe language.
        locales = list(i18n.list_available_locales())
        # Then the list is not empty.
        self.assertTrue(locales)


class TestI18nDefaultLangWebCase(WebCase):
    login = False
    default_config = {'default-lang': 'FR'}

    @classmethod
    def teardown_class(cls):
        # Reset default-lang to avoid issue with other test
        cherrypy.config['tools.i18n.default'] = 'en'
        super().teardown_class()

    def test_default_lang_without_accept_language(self):
        # Given a default language
        # When user connect to the application without Accept-Language
        self.getPage("/login/")
        self.assertStatus(200)
        # Then page is displayed with default lang
        self.assertInBody('lang="fr"')

    def test_default_lang_with_accept_language(self):
        # Given a default language
        # When user connect to the application with Accept-Language English
        self.getPage("/login/", headers=[("Accept-Language", "en-US,en;q=0.8")])
        self.assertStatus(200)
        # Then page is displayed as english
        self.assertInBody('lang="en"')

    def test_default_lang_with_unknown_accept_language(self):
        # Given a default language
        # When user connect to the application with Accept-Language English
        self.getPage("/login/", headers=[("Accept-Language", "it")])
        self.assertStatus(200)
        # Then page is displayed as english
        self.assertInBody('lang="fr"')


class TestI18nInvalidDefaultLangWebCase(WebCase):
    login = False
    default_config = {'default-lang': 'invalid', 'default-timezone': 'invalid'}

    def setUp(self):
        # Manually clear variables between each test
        i18n._current.__dict__.clear()
        return super().setUp()

    def test_default_lang_invalid(self):
        # Given an invalid default language
        # When user connect to the application without Accept-Language
        self.getPage("/login/")
        self.assertStatus(200)
        # Then page is displayed with fallback to "en"
        self.assertInBody('lang="en"')

    def test_default_timezone_invalid(self):
        # Given an invalid default timezone
        print(i18n._current.__dict__)
        print(cherrypy.config.get('tools.i18n.default_timezone'))
        # When getting current timezone
        tzinfo = i18n.get_timezone()
        # Then timezone is None to force usage of serer timezone
        self.assertIsNone(tzinfo)


class TestI18nTimezone(WebCase):

    default_config = {'default-timezone': 'UTC'}

    def setUp(self):
        # Manually clear variables between each test
        i18n._current.__dict__.clear()
        return super().setUp()

    def test_get_timezone(self):
        # When getting current timezone
        tzinfo = i18n.get_timezone()
        # Then timezone is UTC
        self.assertEqual('UTC', str(tzinfo))

    def test_with_preferred_timezone(self):
        with i18n.preferred_lang('en'):
            # Given a date with timezone 'UTC'
            date = datetime.utcfromtimestamp(1680111611).replace(tzinfo=timezone.utc)
            self.assertIn('Coordinated Universal Time', i18n.format_datetime(date, format='full'))
            # When using preferred_lang with french
            with i18n.preferred_timezone('America/Toronto'):
                # Then date time formating used EDT locale
                self.assertIn('Eastern Daylight Time', i18n.format_datetime(date, format='full'))
            # When using preferred_lang with french
            with i18n.preferred_timezone('Europe/Paris'):
                # Then date time formating used EDT locale
                self.assertIn('Central European Summer Time', i18n.format_datetime(date, format='full'))
            # Then outside the block, settings goes back to UTC
            self.assertIn('Coordinated Universal Time', i18n.format_datetime(date, format='full'))

    def test_timezone(self):
        # Given english locale
        date = datetime.utcfromtimestamp(1680111611).replace(tzinfo=timezone.utc)
        with i18n.preferred_lang('en'):
            # When getting list of timezone
            timezones = [
                i18n.format_datetime(date, format='zzzz', tzinfo=timezone)
                for timezone in i18n.list_available_timezones()
            ]
            # Then Central time is displayed
            self.assertIn('Central European Summer Time', timezones)

        # Given french locale
        with i18n.preferred_lang('fr'):
            # When getting list of timezone
            timezones = [
                i18n.format_datetime(date, format='zzzz', tzinfo=timezone)
                for timezone in i18n.list_available_timezones()
            ]
            # Then central time is displayed
            self.assertIn('heure d’été d’Europe centrale', timezones)
