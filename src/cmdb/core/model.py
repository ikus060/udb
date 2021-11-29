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

import cherrypy
import cmdb.tools.db  # noqa: import cherrypy.tools.db
from cmdb.core.passwd import check_password, hash_password
from sqlalchemy import Column, String

Base = cherrypy.tools.db.get_base('sqlite:///www.sqlite')


class UserLoginException(Exception):
    """
    Raised when user's credentials are invalid.
    """
    pass


class User(Base):
    __tablename__ = 'users'

    username = Column(String, primary_key=True)
    password = Column(String)
    email = Column(String, unique=True)

    def __repr__(self):
        return "<User(name='%s', email='%s')>" % (self.name, self.email)

    @classmethod
    def create_default_admin(cls, default_username, default_password):
        """
        If the database is empty, create a default admin user.
        """
        assert default_username
        # count number of users.
        count = cls.query.count()
        if count:
            return  # database is not empty
        # Create default user.
        user = cls(username=default_username,
                   password=default_password or hash_password('admin123'))
        cls.session.add(user)
        return user

    @classmethod
    def login(cls, username, password):
        """
        Validate username password using database and LDAP.
        """
        user = cls.query.filter_by(username=username).first()
        if user and check_password(password, user.password):
            return username
        raise UserLoginException()

    @classmethod
    def create(cls, username, password=None):
        """
        Create a new user in database with the given password.
        """
        assert username
        password = hash_password(password) if password else None
        user = cls(username=username, password=password)
        cls.session.add(user)
        return user
