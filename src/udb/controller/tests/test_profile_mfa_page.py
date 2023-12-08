# -*- coding: utf-8 -*-
# rdiffweb, A web interface to rdiff-backup repositories
# Copyright (C) 2012-2023 rdiffweb contributors
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

from unittest.mock import ANY, MagicMock

import cherrypy
from parameterized import parameterized

from udb.controller.tests import MATCH, WebCase
from udb.core.model import User


class ProfileMfaTest(WebCase):
    login = True

    def setUp(self):
        super().setUp()
        # Define email for all test
        userobj = User.query_user(self.username)
        userobj.email = 'admin@example.com'
        userobj.commit()
        self.wait_for_tasks()
        # Register a listener on email
        self.listener = MagicMock()
        cherrypy.engine.subscribe('queue_mail', self.listener.queue_email, priority=50)
        cherrypy.engine.subscribe('send_mail', self.listener.send_mail, priority=50)

    def tearDown(self):
        cherrypy.engine.unsubscribe('queue_mail', self.listener.queue_email)
        cherrypy.engine.unsubscribe('send_mail', self.listener.send_mail)
        return super().tearDown()

    def _set_mfa(self, mfa):
        # Define mfa for user
        userobj = User.query_user(self.username)
        userobj.mfa = mfa
        userobj.commit()
        # Reset mock.
        self.listener.reset_mock()
        # Leave to disable mfa
        if mfa == User.MFA_DISABLED:
            return
        # Generate a code for login if required
        self.getPage("/mfa/")
        self.assertStatus(200)
        self.assertInBody("A new verification code has been sent to your email.")
        # Extract code from email between <strong> and </strong>
        self.listener.queue_email.assert_called_once()
        message = self.listener.queue_email.call_args[1]['message']
        code = message.split('<strong>', 1)[1].split('</strong>')[0]
        # Login to MFA
        self.getPage("/mfa/", method='POST', body={'code': code, 'submit': '1'})
        self.assertStatus(303)
        # Clear mock.
        self.wait_for_tasks()
        self.listener.reset_mock()

    def _get_code(self, action):
        assert action in ['enable_mfa', 'disable_mfa', 'resend_code']
        # Query MFA page to generate a code
        self.getPage("/profile/mfa", method='POST', body={action: '1'})
        self.assertStatus(200)
        self.assertInBody("A new verification code has been sent to your email.")
        # Extract code from email between <strong> and </strong>
        self.listener.queue_email.assert_called_once()
        message = self.listener.queue_email.call_args[1]['message']
        self.listener.reset_mock()
        return message.split('<strong>', 1)[1].split('</strong>')[0]

    def test_get(self):
        # When getting the page
        self.getPage("/profile/mfa")
        # Then the page is return without error
        self.assertStatus(200)

    @parameterized.expand(
        [
            ('enable_mfa', User.MFA_DISABLED, User.MFA_ENABLED, "*Two-Factor authentication*Enabled*"),
            ('disable_mfa', User.MFA_ENABLED, User.MFA_DISABLED, "*Two-Factor authentication*Disabled*"),
        ]
    )
    def test_with_valid_code(self, action, initial_mfa, expected_mfa, expected_message):
        # Define mfa for user
        self._set_mfa(initial_mfa)
        # Given a user with email requesting a code
        code = self._get_code(action=action)
        # When sending a valid code
        self.getPage("/profile/mfa", method='POST', body={action: '1', 'code': code})
        self.assertStatus(303)
        # Then mfa get enabled or disable accordingly
        self.getPage("/profile/mfa")
        self.assertStatus(200)
        if expected_mfa:
            self.assertInBody('Two-Factor authentication enabled successfully.')
        else:
            self.assertInBody('Two-Factor authentication disabled successfully.')
        userobj = User.query_user(self.username)
        self.assertEqual(userobj.mfa, expected_mfa)
        # Then no verification code get sent
        self.assertNotInBody("A new verification code has been sent to your email.")
        # Then an email confirmation get send
        self.wait_for_tasks()
        self.listener.send_mail.assert_called_once_with(to=userobj.email, subject=ANY, message=MATCH(expected_message))
        # Then next page request is still working.
        self.getPage('/dashboard/')
        self.assertStatus(200)

    def test_with_valid_code_including_spaces(self):
        # Define mfa for user
        self._set_mfa(False)
        # Given a user with email requesting a code
        code = self._get_code('enable_mfa')
        # When sending a valid code with extra spaces
        self.getPage("/profile/mfa", method='POST', body={'enable_mfa': '1', 'code': ' ' + code + ' '})
        self.assertStatus(303)
        # Then mfa get enabled or disable accordingly
        self.getPage("/profile/mfa")
        self.assertStatus(200)
        self.assertInBody('Two-Factor authentication enabled successfully.')

    @parameterized.expand(
        [
            ('enable_mfa', User.MFA_DISABLED, User.MFA_DISABLED),
            ('disable_mfa', User.MFA_ENABLED, User.MFA_ENABLED),
        ]
    )
    def test_with_invalid_code(self, action, initial_mfa, expected_mfa):
        # Define mfa for user
        self._set_mfa(initial_mfa)
        # Given a user with email requesting a code
        self._get_code(action=action)
        # When sending an invalid code
        self.getPage("/profile/mfa", method='POST', body={action: '1', 'code': '1234567'})
        # Then mfa get enabled or disable accordingly
        self.assertStatus(200)
        userobj = User.query_user(self.username)
        self.assertEqual(userobj.mfa, expected_mfa)
        # Then next page request is still working.
        self.getPage('/dashboard/')
        self.assertStatus(200)

    @parameterized.expand(
        [
            ('enable_mfa', User.MFA_DISABLED),
            ('disable_mfa', User.MFA_ENABLED),
        ]
    )
    def test_without_email(self, action, initial_mfa):
        # Define mfa for user
        self._set_mfa(initial_mfa)
        # Given a user without email requesting a code
        userobj = User.query_user(self.username)
        userobj.email = ''
        userobj.commit()
        # When trying to enable or disable mfa
        self.getPage("/profile/mfa", method='POST', body={action: '1'})
        # Then an error is return to the user
        self.assertStatus(200)
        self.assertInBody("To continue, you must set up an email address for your account.")

    @parameterized.expand(
        [
            (User.MFA_DISABLED,),
            (User.MFA_ENABLED,),
        ]
    )
    def test_resend_code(self, initial_mfa):
        # Define mfa for user
        self._set_mfa(initial_mfa)
        # When requesting a new code.
        self.getPage("/profile/mfa", method='POST', body={'resend_code': '1'})
        # Then a new code get sent.
        userobj = User.query_user(self.username)
        self.listener.queue_email.assert_called_once_with(
            to=userobj.email, subject="Your verification code", message=ANY
        )
        # Then A success message is displayedto the user.
        self.assertInBody("A new verification code has been sent to your email.")
