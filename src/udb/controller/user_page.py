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
from wtforms.fields import SelectField, StringField
from wtforms.validators import data_required, email, optional

from udb.core.model import User
from udb.tools.i18n import gettext as _

from .form import CherryForm


class UserForm(CherryForm):

    object_cls = User

    username = StringField(_('Username'), validators=[data_required()])

    fullname = StringField(_('Fullname'))

    email = StringField(_('Email'), validators=[optional(), email()])

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
