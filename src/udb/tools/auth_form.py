# udb, A web interface to manage IT network
# Copyright (C) 2022-2025 IKUS Software inc.
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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import urllib.parse

import cherrypy

LOGIN_REDIRECT_URL = '_auth_form_redirect_url'


class CheckAuthForm(cherrypy.Tool):
    def __init__(self, priority=73):
        super().__init__(point='before_handler', callable=self.run, priority=priority)

    def _get_redirect_url(self):
        """Get reference to current URL"""
        request = cherrypy.serving.request
        uri_encoding = getattr(request, 'uri_encoding', 'utf-8')
        original_url = urllib.parse.quote(request.path_info, encoding=uri_encoding)
        qs = request.query_string
        return cherrypy.url(original_url, qs=qs, base='')

    def get_original_url(self):
        """
        Return the original URL browsed by the user before authentication.
        """
        return cherrypy.serving.session.get(LOGIN_REDIRECT_URL)

    def redirect_to_form_url(self, form_url=None):
        """
        Called to redirect user to login form.
        """
        session = cherrypy.serving.session
        session[LOGIN_REDIRECT_URL] = self._get_redirect_url()
        form_url = form_url or cherrypy.request.config.get('tools.auth_form.form_url', '/login/')
        raise cherrypy.HTTPRedirect(form_url)

    def redirect_to_original_url(self):
        # Redirect user to original URL
        redirect_url = self.get_original_url() or '/'
        raise cherrypy.HTTPRedirect(redirect_url)

    def run(self, session_user_key, form_url='/login/'):
        """
        A tool that verify if the session is associated to a user by tracking
        a session key. If session is not authenticated, redirect user to login page.
        """

        # Verify if session is enabled, if not the user is not authenticated.
        if not hasattr(cherrypy.serving, 'session'):
            raise cherrypy.HTTPRedirect(form_url)

        # When session's login is defined, the user is authenticated.
        session = cherrypy.serving.session
        login = session.get(session_user_key)
        if not login and cherrypy.request.path_info != form_url:
            # Store original URL and redirect to login page
            self.redirect_to_form_url(form_url)
            return

        # When authenticated, store current login name in request.
        cherrypy.request.login = login

    def login(self, username):
        """
        Must be called by the page hanlder when the authentication is successful.
        """
        # Store session data
        session_user_key = cherrypy.request.config.get('tools.auth_form.session_user_key')
        session = cherrypy.serving.session
        session[session_user_key] = username
        # Generate a new session id
        session.regenerate()

    def clear_login_identity(self):
        """
        Clear the loging information, and generate a new session id.
        """
        session_user_key = cherrypy.request.config.get('tools.auth_form.session_user_key')
        session = cherrypy.serving.session
        session.pop(session_user_key, None)
        session.regenerate()

    def clear_session(self):
        """
        Clear session data and generate a new session id.
        """
        session = cherrypy.serving.session
        session.clear()
        session.regenerate()


cherrypy.tools.auth_form = CheckAuthForm()
