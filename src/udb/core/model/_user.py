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

import cherrypy
import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.core.passwd import check_password, hash_password
from sqlalchemy import Column, String
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.schema import Index
from sqlalchemy.sql.sqltypes import Boolean, Integer

Base = cherrypy.tools.db.get_base()


class UserLoginException(Exception):
    """
    Raised when user's credentials are invalid.
    """
    pass


class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    # Unique
    username = Column(String)
    password = Column(String, nullable=True)
    fullname = Column(String, nullable=False, default='')
    email = Column(String, nullable=True, unique=True)
    deleted = Column(Boolean, default=False)

    def __repr__(self):
        return "<User(name='%s', email='%s')>" % (self.username, self.email)

    def __html__(self):
        # TODO Not sure if we keep this here.
        return self.fullname or self.username

    @classmethod
    def create_default_admin(cls, default_username, default_password):
        """
        If the database is empty, create a default admin user.
        """
        assert default_username
        # count number of users.
        count = cls.query.count()
        if count:
            return None  # database is not empty
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


# Create a unique index for username
Index('user_username_index', func.lower(User.username), unique=True)
