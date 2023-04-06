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

import logging

import cherrypy
from cherrypy.process.plugins import SimplePlugin

from udb.core.model import User

logger = logging.getLogger(__name__)


class LoginPlugin(SimplePlugin):
    """
    This plugins register an "authenticate" listener to validate
    username and password of users. In addition, it provide a "login"
    listener to authenticate and possibly create the user in database.
    """

    add_missing_user = False
    add_user_default_role = 'guest'
    admin_group = None
    dnszone_mgmt_group = None
    subnet_mgmt_group = None
    user_group = None
    guest_group = None

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
        if user and user.check_password(password):
            return username, {}
        return False

    def _get_user_role(self, member_of):
        """
        Look for user role based on group member ship.
        """
        if member_of is None:
            return None
        group_map = [
            ('admin', self.admin_group),
            ('dnszone-mgmt', self.dnszone_mgmt_group),
            ('subnet-mgmt', self.dnszone_mgmt_group),
            ('user', self.user_group),
            ('guest', self.guest_group),
        ]
        for role, groups in group_map:
            if groups and member_of and set(groups) & set(member_of):
                return role
        return None

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
        extra_attrs = authenticates[0][1]
        fullname = extra_attrs.get('_fullname', None)
        email = extra_attrs.get('_email', None)
        member_of = extra_attrs.get('_member_of', None)
        role = self._get_user_role(member_of)
        # When enabled, create missing userobj in database.
        userobj = User.query.filter_by(username=username).first()
        if userobj is None and self.add_missing_user:
            try:
                # At this point, we need to create a new user in database.
                # In case default values are invalid, let evaluate them
                # before creating the user in database.
                userobj = User(username=real_username, role=self.add_user_default_role).add().commit()
            except Exception:
                logger.warning('fail to create new user', exc_info=1)
        if userobj is None:
            # User doesn't exists in database
            return None

        # Update user attributes
        self._update_user(userobj, role=role, fullname=fullname, email=email)

        self.bus.publish('user_login', userobj)
        return userobj

    def _update_user(self, userobj, role, fullname, email):
        """
        Update user's attributes from external source.
        """
        if role and userobj.role != role:
            userobj.role = role
            userobj.add().commit()
        if fullname and userobj.fullname != fullname:
            userobj.fullname = fullname
            userobj.add().commit()
        if email and userobj.email != email:
            userobj.email = email
            userobj.add().commit()


cherrypy.login = LoginPlugin(cherrypy.engine)
cherrypy.login.subscribe()

cherrypy.config.namespaces['login'] = lambda key, value: setattr(cherrypy.login, key, value)
