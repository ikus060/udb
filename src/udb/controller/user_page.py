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
from wtforms.fields import PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional

from udb.core.model import User
from udb.tools.i18n import gettext as _

from .common_page import CommonPage
from .form import CherryForm


class UserForm(CherryForm):

    object_cls = User

    username = StringField(_('Username'), validators=[DataRequired(), Length(max=256)])

    fullname = StringField(_('Fullname'), validators=[Length(max=256)])

    email = StringField(_('Email'), validators=[Optional(), Email(), Length(max=256)])

    role = SelectField(
        _('Role'),
        coerce=int,
        default=User.ROLE_GUEST,
        choices=[
            (User.ROLE_GUEST, _('Guest - Permissions to view the records')),
            (User.ROLE_USER, _('User - Permissions to view and edit records')),
            (User.ROLE_ADMIN, _('Administrator - All permissions')),
        ],
    )

    password = PasswordField(
        _('Password'),
        validators=[Optional(), Length(max=256)],
        description=_(
            'To create a local user, set a password. To create an external user, validating the password with LDAP, do not set a password.'
        ),
    )

    clear_password = SubmitField(_('Clear password'))

    def populate_obj(self, obj):
        obj.username = self.username.data
        obj.fullname = self.fullname.data
        obj.email = self.email.data
        obj.role = self.role.data
        if self.clear_password.data:
            obj.password = None
        elif self.password.data:
            obj.set_password(self.password.data)


class UserPage(CommonPage):
    def __init__(self) -> None:
        super().__init__(User, UserForm, list_role=User.ROLE_ADMIN, edit_role=User.ROLE_ADMIN)

    def _list_query(self):
        return User.query.with_entities(
            User.id,
            User.status,
            User.username,
            User.fullname,
            User.email,
            User.role,
        )
