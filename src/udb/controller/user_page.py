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
from udb.tools.i18n import get_timezone_name, gettext
from udb.tools.i18n import gettext_lazy as _
from udb.tools.i18n import list_available_locales, list_available_timezones

from .common_page import CommonPage
from .form import CherryForm


class NewUserForm(CherryForm):

    object_cls = User

    username = StringField(
        _('Username'),
        validators=[DataRequired(), Length(max=256)],
    )

    fullname = StringField(_('Fullname'), validators=[Length(max=256)], render_kw={"autofocus": True})

    email = StringField(_('Email'), validators=[Optional(), Email(), Length(max=256)])

    lang = SelectField(_('Preferred Language'), default='')

    timezone = SelectField(_('Preferred Time zone'), default='')

    role = SelectField(_('Role'), default='guest')

    password = PasswordField(
        _('Password'),
        validators=[Optional(), Length(max=256)],
        description=_(
            'To create a local user, set a password. To create an external user, validating the password with LDAP, do not set a password.'
        ),
    )

    clear_password = SubmitField(_('Clear password'), render_kw={"class": "btn-secondary"})

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Load available languages
        languages = [(locale.language, locale.display_name.capitalize()) for locale in list_available_locales()]
        languages = sorted(languages, key=lambda x: x[1])
        languages.insert(0, ('', _('(default)')))
        self.lang.choices = languages
        # Load available timezone
        timezones = [
            (timezone, '%s (%s)' % (timezone, get_timezone_name(timezone))) for timezone in list_available_timezones()
        ]
        timezones.insert(0, ('', _('(default)')))
        self.timezone.choices = timezones
        # Define available roles
        self.role.choices = [
            ('guest', gettext('Guest - Permissions to view the records')),
            ('user', gettext('User - Permissions to view and edit records')),
            ('dnszone-mgmt', gettext('DNS Zone Manager - Permissions to create a new DNS zone')),
            ('subnet-mgmt', gettext('Subnet Manager - Permissions to create new Subnet')),
            ('admin', gettext('Administrator - All permissions including user')),
        ]

    def populate_obj(self, obj):
        obj.username = self.username.data
        obj.fullname = self.fullname.data
        obj.email = self.email.data
        obj.role = self.role.data
        obj.lang = self.lang.data
        obj.timezone = self.timezone.data
        if self.clear_password.data:
            obj.password = None
        elif self.password.data:
            obj.set_password(self.password.data)


class EditUserForm(NewUserForm):
    """
    Make username field read only when editing user.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.username.render_kw = {"readonly": True, "disabled": True}


class UserPage(CommonPage):
    def __init__(self) -> None:
        super().__init__(
            User,
            EditUserForm,
            NewUserForm,
            list_perm=User.PERM_USER_MGMT,
            edit_perm=User.PERM_USER_MGMT,
            new_perm=User.PERM_USER_MGMT,
        )

    def _list_query(self):
        return User.query.with_entities(
            User.id,
            User.estatus,
            User.username,
            User.fullname,
            User.email,
            User.role,
        )
