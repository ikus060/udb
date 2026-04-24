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

import logging

import cherrypy
from cherrypy_foundation.passwd import check_password, hash_password
from cherrypy_foundation.tools.i18n import gettext_lazy as _
from sqlalchemy import Column, String, case, event, inspect
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import deferred, validates
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.schema import Index
from sqlalchemy.sql.sqltypes import Integer

from ._json import JsonMixin
from ._message import MessageMixin
from ._status import StatusMixing
from ._update import column_add, column_exists
from ._url import UrlMixin

# Debian trixie drop python3-zxcvbn.
# Until further notice, let use zxcvbn-rs-py as a replacement
try:
    from zxcvbn import zxcvbn
except ImportError:
    from zxcvbn_rs_py import zxcvbn as _zxcvbn

    def zxcvbn(password):
        # Return a dict.
        entropy = _zxcvbn(password)
        return {
            'score': int(entropy.score),
            'feedback': (
                {
                    'warning': str(entropy.feedback.warning),
                    'suggestions': map(str, entropy.feedback.suggestions),
                }
                if entropy.feedback
                else {}
            ),
        }


logger = logging.getLogger(__name__)

Base = cherrypy.db.base


class User(JsonMixin, StatusMixing, MessageMixin, UrlMixin, Base):
    __tablename__ = 'user'

    MFA_DISABLED = 0
    MFA_ENABLED = 1

    # Define permissions.
    PERM_USER_MGMT = 1
    PERM_SUBNET_CREATE = 1 << 2
    PERM_DNSZONE_CREATE = 1 << 3
    PERM_NETWORK_EDIT = 1 << 4
    PERM_NETWORK_LIST = 1 << 5
    PERM_ENVIRONMENT_EDIT = 1 << 6
    PERM_RULE_EDIT = 1 << 7

    # Define role using permissions
    ROLE_GUEST = PERM_NETWORK_LIST
    ROLE_USER = ROLE_GUEST | PERM_NETWORK_EDIT
    ROLE_DNSZONE_MGMT = ROLE_USER | PERM_DNSZONE_CREATE
    ROLE_SUBNET_MGMT = ROLE_DNSZONE_MGMT | PERM_SUBNET_CREATE
    ROLE_ADMIN = ROLE_SUBNET_MGMT | PERM_USER_MGMT | PERM_ENVIRONMENT_EDIT | PERM_RULE_EDIT

    # Define roles using a name
    ROLES = {
        'guest': ROLE_GUEST,
        'user': ROLE_USER,
        'dnszone-mgmt': ROLE_DNSZONE_MGMT,
        'subnet-mgmt': ROLE_SUBNET_MGMT,
        'admin': ROLE_ADMIN,
    }

    id = Column(Integer, primary_key=True)
    # Unique
    username = Column(String)
    password = deferred(Column(String, nullable=True))
    fullname = Column(String, nullable=False, default='')
    email = Column(String, nullable=False, default='')
    role = Column(String, nullable=False, default='guest')
    lang = Column(String, nullable=False, default='')
    timezone = Column(String, nullable=False, default='', server_default='')
    mfa = Column(Integer, nullable=False, default=MFA_DISABLED, server_default=str(MFA_DISABLED))

    @classmethod
    def authenticate(cls, login, password):
        """
        Verify username password against local database.
        """
        # Check user password.
        userobj = cls.query_user(login)
        return userobj and userobj.check_password(password)

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
        user = cls(username=default_username, password=password, role='admin')
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
    def _get_user_role(cls, member_of):
        """
        Look for user role based on group member ship.
        """
        if member_of is None:
            return None
        cfg = cherrypy.tree.apps[''].cfg
        group_map = [
            ('admin', cfg.ldap_admin_group),
            ('dnszone-mgmt', cfg.ldap_dnszone_mgmt_group),
            ('subnet-mgmt', cfg.ldap_subnet_mgmt_group),
            ('user', cfg.ldap_user_group),
            ('guest', cfg.ldap_guest_group),
        ]
        for role, groups in group_map:
            if groups and member_of and set(groups) & set(member_of):
                return role
        return None

    @classmethod
    def get_create_or_update_user(cls, login, user_info=None):
        """
        Used during authentication process to search for existing user,
        create user if missing and update user if required.
        """
        # Validate credentials.
        fullname = user_info.get('_fullname', None)
        email = user_info.get('_email', None)
        member_of = user_info.get('_member_of', None)
        role = cls._get_user_role(member_of)
        # When enabled, create missing userobj in database.
        userobj = cls.query_user(login)
        cfg = cherrypy.tree.apps[''].cfg
        if userobj is None and cfg.add_missing_user:
            try:
                # At this point, we need to create a new user in database.
                # In case default values are invalid, let evaluate them
                # before creating the user in database.
                userobj = User(username=login, role=cfg.add_user_default_role).add().commit()
            except Exception:
                logger.warning('fail to create new user', exc_info=1)
        if userobj is None:
            # User doesn't exists in database
            return None

        # Update user attributes
        if role and userobj.role != role:
            userobj.role = role
            userobj.add().commit()
        if fullname and userobj.fullname != fullname:
            userobj.fullname = fullname
            userobj.add().commit()
        if email and userobj.email != email:
            userobj.email = email
            userobj.add().commit()
        return userobj.username, userobj

    def is_admin(self):
        """
        Return true if this user is an administrator
        """
        return self.role == 'admin'

    def has_permissions(self, perm):
        assert isinstance(perm, int)
        current_perm = User.ROLES.get(self.role, 0)
        return (current_perm | perm) == current_perm

    @hybrid_property
    def summary(self):
        return self.fullname or self.username

    @summary.expression
    def summary(cls):
        return case((cls.fullname != '', cls.fullname), else_=cls.username)

    def check_password(self, password):
        return check_password(password, self.password)

    @classmethod
    def query_user(cls, username):
        """
        Used to query user database for authentication.
        """
        return User.query.filter(
            func.lower(User.username) == username.lower(),
            User.estatus == User.STATUS_ENABLED,
        ).first()

    def set_password(self, new_password):
        if not new_password:
            raise ValueError('new_password', _("New password cannot be empty."))

        # Verify password score using zxcvbn
        cfg = cherrypy.tree.apps[''].cfg
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

    @validates('role')
    def validate_role(self, key, value):
        if value not in User.ROLES:
            raise ValueError('invalid role')
        return value

    def add_change(self, new_message):
        """
        Hide changes made to password field.
        """
        changes = new_message.changes
        if 'password' in changes:
            changes['password'] = ['unknown', '•••••••']
            new_message.changes = changes
        super().add_change(new_message)


# Create a unique index for username
Index(
    'user_username_unique_ix',
    func.lower(User.username),
    unique=True,
    info={
        'description': _('This username already exists.'),
        'field': 'username',
        'related': lambda obj: User.query.filter(func.lower(User.username) == func.lower(obj.username)).first(),
    },
)


@event.listens_for(User, "before_update")
def user_before_update(mapper, connection, instance):
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


@event.listens_for(Base.metadata, 'after_create')
def create_mfa_field(target, conn, **kw):
    if not column_exists(conn, User.mfa):
        column_add(conn, User.mfa)
