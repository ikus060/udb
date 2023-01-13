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

import cherrypy
from sqlalchemy import Column, String, case, event, inspect
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import deferred
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.schema import Index
from sqlalchemy.sql.sqltypes import Integer
from zxcvbn import zxcvbn

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.core.passwd import check_password, hash_password
from udb.tools.i18n import gettext_lazy as _

from ._json import JsonMixin
from ._status import StatusMixing

Base = cherrypy.tools.db.get_base()


class User(JsonMixin, StatusMixing, Base):
    __tablename__ = 'user'

    ROLE_ADMIN = 0
    ROLE_USER = 5
    ROLE_GUEST = 10

    id = Column(Integer, primary_key=True)
    # Unique
    username = Column(String)
    password = deferred(Column(String, nullable=True))
    fullname = Column(String, nullable=False, default='')
    email = Column(String, nullable=True, unique=True)
    role = Column(Integer, nullable=True, default=ROLE_GUEST)

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
        password = default_password or 'admin123'
        if not password.startswith('{SSHA}'):
            password = hash_password(password)
        user = cls(username=default_username, password=password, role=User.ROLE_ADMIN)
        return user.add()

    @classmethod
    def create(cls, username, password=None, **kwargs):
        """
        Create a new user in database with the given password.
        """
        assert username
        password = hash_password(password) if password else None
        user = cls(username=username, password=password, **kwargs)
        return user.add()

    @classmethod
    def coerce_role_name(cls, name):
        return {'admin': User.ROLE_ADMIN, 'user': User.ROLE_USER, 'guest': User.ROLE_GUEST}.get(name)

    def is_local(self):
        """
        True if the user authentication is local.
        """
        return self.password is not None

    def is_admin(self):
        """
        Return true if this user is an administrator
        """
        return self.role == User.ROLE_ADMIN

    def is_user(self):
        """Return True if this user has role `user` or `admin`."""
        return self.role <= User.ROLE_USER

    def is_guest(self):
        """Return True if this user has role `guest`, `user` or `admin`."""
        return self.role <= User.ROLE_GUEST

    def has_role(self, role):
        assert isinstance(role, int)
        return self.role <= role

    def allow_new_record(self):
        return self.is_user()

    def allow_edit_record(self):
        return self.is_user()

    @hybrid_property
    def summary(self):
        return self.fullname or self.username

    @summary.expression
    def summary(cls):
        return case((cls.fullname != '', cls.fullname), else_=cls.username)

    def check_password(self, password):
        return check_password(password, self.password)

    def set_password(self, new_password):
        if not new_password:
            raise ValueError('new_password', _("New password cannot be empty."))

        # Verify password score using zxcvbn
        cfg = cherrypy.tree.apps[''].root.cfg
        stats = zxcvbn(new_password)
        if stats.get('score') < cfg.password_score:
            msg = _('Password too weak.')
            warning = stats.get('feedback', {}).get('warning')
            suggestions = stats.get('feedback', {}).get('suggestions')
            if warning:
                msg += ' ' + warning
            if suggestions:
                msg += ' ' + ' '.join(suggestions)
            raise ValueError('new_password', msg)

        self.password = hash_password(new_password)

    def __str__(self):
        return self.fullname or self.username

    def to_json(self):
        data = super().to_json()
        if 'password' in data:
            del data['password']
        return data


# Create a unique index for username
Index('user_username_index', func.lower(User.username), unique=True)


@event.listens_for(User, "before_update")
def before_update(mapper, connection, instance):
    # Check if current instance matches our current user
    currentuser = getattr(cherrypy.serving.request, 'currentuser', None)
    if currentuser and currentuser.id == instance.id:
        # Raise exception when current user try to updated it's own status
        state = inspect(instance)
        if state.attrs['status'].history.has_changes():
            raise ValueError('status', _('A user cannot update his own status.'))
        # Raise exception when current user try to updated it's own role
        if state.attrs['role'].history.has_changes():
            raise ValueError('role', _('A user cannot update his own role.'))
