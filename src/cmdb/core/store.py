# -*- coding: utf-8 -*-
# cmdb, A web interface to manage IT network CMDB
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

from cmdb.core.passwd import check_password, hash_password
from .model import User
import cherrypy


class UserLoginException(Exception):
    """
    Raised when user's credentials are invalid.
    """
    pass


def _session():
    if hasattr(cherrypy.request, 'session'):
        return cherrypy.request.session
    return cherrypy.tools.db.session


def user_login(username, password):
    """
    Validate username password using database and LDAP.
    """
    user = _session().query(User).filter_by(username=username).first()
    if user and check_password(password, user.password):
        return username
    raise UserLoginException()


def create_user(username, password):
    """
    Create a new user in database with the given password.
    """
    user = User(username=username, password=hash_password(password))
    _session().add(user)
