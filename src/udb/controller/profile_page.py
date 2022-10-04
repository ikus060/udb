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
from wtforms.fields import PasswordField, StringField
from wtforms.validators import DataRequired, Email, EqualTo, InputRequired, Length, Optional, ValidationError

from udb.controller import flash
from udb.controller.form import CherryForm
from udb.core.model import User
from udb.tools.i18n import gettext as _


class AccountForm(CherryForm):

    username = StringField(
        _('Username'),
        validators=[
            DataRequired(),
            Length(max=256),
        ],
        render_kw={'readonly': True},
    )

    fullname = StringField(
        _('Fullname'),
        validators=[
            Length(max=256),
        ],
    )

    email = StringField(
        _('Email'),
        validators=[
            Optional(),
            Email(),
            Length(max=256),
        ],
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Make username field read_only
        self.username.process = lambda *args, **kwargs: None
        self.username.populate_obj = lambda *args, **kwargs: None


class PasswordForm(CherryForm):

    current_password = PasswordField(
        _('Current password'),
        validators=[
            InputRequired(_("Current password is missing.")),
            Length(max=256),
        ],
        description=_('You must provide your current password in order to change it.'),
    )

    new_password = PasswordField(
        _('New password'),
        validators=[
            InputRequired(_("New password is missing.")),
            EqualTo('password_confirmation', message=_("The new password and its confirmation do not match.")),
            Length(max=256),
        ],
    )

    password_confirmation = PasswordField(
        _('Password confirmation'),
        validators=[
            InputRequired(_("Confirmation password is missing.")),
            Length(max=256),
        ],
    )

    def validate_current_password(self, field):
        # If current password is undefined, it's a remote user
        userobj = cherrypy.request.currentuser
        if userobj.password is None:
            raise ValidationError(
                _('Cannot update password for non-local user. Contact your administrator for more detail.')
            )

        # Verify if the current password matches current password database
        if not userobj.check_password(field.data):
            raise ValidationError(_('Current password is not valid.'))

    def populate_obj(self, userobj):
        userobj.set_password(self.new_password.data)


class ProfilePage:
    @cherrypy.expose()
    @cherrypy.tools.jinja2(template=['profile.html'])
    def index(self, **kwargs):
        userobj = cherrypy.request.currentuser
        account_form = AccountForm(obj=userobj)
        password_form = PasswordForm()
        if 'current_password' in kwargs:
            form = password_form
        else:
            form = account_form

        # Update object if form was submited
        if form.validate_on_submit():
            try:
                form.populate_obj(userobj)
                userobj.add()
            except ValueError as e:
                # raised by SQLAlchemy validators
                User.session.rollback()
                if len(e.args) == 2 and getattr(form, e.args[0], None):
                    getattr(form, e.args[0]).errors.append(e.args[1])
                else:
                    flash(_('Invalid value: %s') % e, level='error')
            else:
                flash(_('User profile updated successfully.'), level='success')
                raise cherrypy.HTTPRedirect("")

        return {'form': account_form, 'password_form': password_form}
