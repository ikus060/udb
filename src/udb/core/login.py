# -*- coding: utf-8 -*-
# udb, A web interface to manage IT network
# Copyright (C) 2021 IKUS Software inc.
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

import logging

import cherrypy
from cherrypy.process.plugins import SimplePlugin
from udb.core.model import User
from udb.core.passwd import check_password
from udb.tools.auth_form import SESSION_KEY

logger = logging.getLogger(__name__)


class LoginPlugin(SimplePlugin):
    """
    This plugins register an "authenticate" listener to validate
    username and password of users. In addition, it provide a "login"
    listener to authenticate and possibly create the user in database.
    """

    add_missing_user = False
    add_user_default_role = User.ROLE_GUEST

    def start(self):
        self.bus.log('Start Login plugin')
        self.bus.subscribe("authenticate", self.authenticate)
        self.bus.subscribe("login", self.login)

    def stop(self):
        self.bus.log('Stop Login plugin')
        self.bus.unsubscribe("authenticate", self.authenticate)
        self.bus.unsubscribe("login", self.login)

    def authenticate(self, username, password):
        """
        Only verify the user's credentials using the database store.
        """
        user = User.query.filter_by(username=username).first()
        if user and check_password(password, user.password):
            return username, {}
        return False

    def login(self, username, password):
        """
        Validate username password using database and LDAP.
        """
        # Validate credentials.
        authenticates = self.bus.publish('authenticate', username, password)
        authenticates = [a for a in authenticates if a]
        if not authenticates:
            return None
        real_username = authenticates[0][0]
        # When enabled, create missing userobj in database.
        userobj = User.query.filter_by(username=username).first()
        if userobj is None and self.add_missing_user:
            try:
                # At this point, we need to create a new user in database.
                # In case default values are invalid, let evaluate them
                # before creating the user in database.
                userobj = User(
                    username=real_username,
                    role=self.add_user_default_role)
                User.session.add(userobj)
                User.session.commit()
            except Exception:
                logger.warning('fail to create new user', exc_info=1)

        # TODO Update user attributes from LDAP ? e.g.: Email and full name ?

        # Save username in session if session is enabled.
        if cherrypy.request.config and cherrypy.request.config.get('tools.sessions.on', False):
            cherrypy.session[SESSION_KEY] = userobj.username
        self.bus.publish('user_login', userobj)
        return userobj


cherrypy.login = LoginPlugin(cherrypy.engine)
cherrypy.login.subscribe()

cherrypy.config.namespaces['login'] = lambda key, value: setattr(
    cherrypy.login, key, value)
