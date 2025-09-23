# udb, A web interface to rdiff-backup repositories
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

import datetime
import time

import cherrypy
from cherrypy.lib import httputil

SESSION_PERSISTENT = '_session_persistent'
SESSION_START_TIME = '_session_start_time'


class SessionsTimeout(cherrypy.Tool):
    """
    This tools allow fine grain control over session timeout.
    """

    def __init__(self, priority=70):
        super().__init__(point='before_handler', callable=self.run, priority=priority)

    def _update_session_timeout(self, persistent_timeout, absolute_timeout):
        # Define the session start time if missing.
        session = cherrypy.serving.session
        if SESSION_START_TIME not in session:
            session[SESSION_START_TIME] = session.now()

        now = session.now()
        if session.get(SESSION_PERSISTENT, False):
            # Persistent session: use fixed expiration
            expiration = session[SESSION_START_TIME] + datetime.timedelta(minutes=persistent_timeout)
            max_age = int((expiration - now).total_seconds())
            session.timeout = max_age // 60

            cookie = cherrypy.serving.response.cookie
            cookie['session_id']['max-age'] = max_age
            cookie['session_id']['expires'] = httputil.HTTPDate(time.time() + max_age)
        else:
            # Non-persistent session: apply idle and absolute timeout limits
            idle_timeout = cherrypy.request.config.get('tools.sessions.timeout', 60)
            expiration_idle = now + datetime.timedelta(minutes=idle_timeout)
            expiration_absolute = session[SESSION_START_TIME] + datetime.timedelta(minutes=absolute_timeout)
            expiration = min(expiration_idle, expiration_absolute)

            max_age = int((expiration - now).total_seconds())
            session.timeout = max_age // 60

        # Regenerate the session if expired.
        if session.timeout <= 0:
            session.clear()
            session.timeout = absolute_timeout
            session.regenerate()

    def run(self, persistent_timeout=43200, absolute_timeout=60):
        # Verify if session is enabled, if not skip execution
        if not hasattr(cherrypy.serving, 'session'):
            return False

        # If login is persistent, update the cookie max-age/expires
        self._update_session_timeout(persistent_timeout, absolute_timeout)

    def set_persistent(self, value=True):
        """
        Make this session persistent.
        """
        # Store session data
        session = cherrypy.serving.session
        session[SESSION_PERSISTENT] = value
        session[SESSION_START_TIME] = session.now()
        # Get timeout configuration.
        config = cherrypy.request.config
        persistent_timeout = config.get('tools.auth_form.persistent_timeout', 43200)
        absolute_timeout = config.get('tools.auth_form.absolute_timeout', 30)
        # Update the session timeout
        self._update_session_timeout(persistent_timeout, absolute_timeout)

    def is_persistent(self):
        """
        Return True if the session is marked to be persistent.
        """
        return cherrypy.serving.session.get(SESSION_PERSISTENT, False)


cherrypy.tools.sessions_timeout = SessionsTimeout()
