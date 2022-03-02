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
from udb.controller import flash
from udb.controller.form import CherryForm
from udb.core.passwd import check_password, hash_password
from udb.tools.i18n import gettext as _
from wtforms.fields import PasswordField, StringField
from wtforms.validators import (ValidationError, data_required, email,
                                equal_to, input_required, optional)


class AccountForm(CherryForm):

    username = StringField(_('Username'), validators=[data_required()], render_kw={'readonly': True})

    fullname = StringField(_('Fullname'))

    email = StringField(_('Email'), validators=[optional(), email()])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Make username field read_only
        self.username.process = lambda *args, **kwargs: None
        self.username.populate_obj = lambda *args, **kwargs: None


class PasswordForm(CherryForm):

    current_password = PasswordField(_('Current password'), validators=[input_required(_("Current password is missing."))], description=_('You must provide your current password in order to change it.'))

    new_password = PasswordField(_('New password'), validators=[input_required(_("New password is missing.")), equal_to('password_confirmation', message=_("The new password and its confirmation do not match."))])

    password_confirmation = PasswordField(_('Password confirmation'), validators=[input_required(_("Confirmation password is missing."))])

    def validate_current_password(self, field):
        # If current password is undefined, it's a remote user
        if cherrypy.request.currentuser.password is None:
            raise ValidationError(_('Cannot update password for non-local user. Contact your administrator for more detail.'))

        # Verify if the current password matches current password database
        if not check_password(field.data, cherrypy.request.currentuser.password):
            raise ValidationError(_('Current password is not valid.'))

    def populate_obj(self, userobj):
        userobj.password = hash_password(self.new_password.data)


class ProfilePage():

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
                self.model.session.rollback()
                if len(e.args) == 2 and getattr(form, e.args[0], None):
                    getattr(form, e.args[0]).errors.append(e.args[1])
                else:
                    flash(_('Invalid value: %s') % e, level='error')
            else:
                flash(_('User profile updated successfully.'), level='success')

        return {
            'form': account_form,
            'password_form': password_form
        }
