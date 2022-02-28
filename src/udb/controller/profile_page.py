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
from udb.controller import flash, url_for
from udb.controller.form import CherryForm
from udb.tools.i18n import gettext as _
from wtforms.fields import PasswordField, StringField
from wtforms.validators import (data_required, email, equal_to, input_required,
                                optional)


class AccountForm(CherryForm):

    username = StringField(_('Username'), validators=[data_required()])

    fullname = StringField(_('Fullname'))

    email = StringField(_('Email'), validators=[optional(), email()])


class PasswordForm(CherryForm):

    current_password = PasswordField(_('Current password'), validators=[input_required(_("Current password is missing."))], description=_('You must provide your current password in order to change it.'))

    new_password = PasswordField(_('New password'), validators=[input_required(_("New password is missing.")), equal_to('password_confirmation', message=_("The new password and its confirmation do not match."))])

    password_confirmation = PasswordField(_('Password confirmation'), validators=[input_required(_("Confirmation password is missing."))])


class ProfilePage():

    @cherrypy.expose()
    @cherrypy.tools.jinja2(template=['profile.html'])
    def index(self):
        # Update object if form was submited
        userobj = cherrypy.request.currentuser
        form = AccountForm(obj=userobj)
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
                raise cherrypy.HTTPRedirect(url_for(self.model))

        return {
            'form': form,
            'password_form': PasswordForm(),
        }

    def password(self, **kwargs):
        userobj = cherrypy.request.currentuser
        form = PasswordForm(obj=userobj)
        if form.validate_on_submit():
            try:
                if userobj.password == form.current_password.data:
                    userobj.password = form.current_password.data
                    userobj.add()
                else:
                    flash(_(' You must provide a valid current password'))
            except ValueError as e:
                # raised by SQLAlchemy validators
                self.model.session.rollback()
                if len(e.args) == 2 and getattr(form, e.args[0], None):
                    getattr(form, e.args[0]).errors.append(e.args[1])
                else:
                    flash(_('Invalid value: %s') % e, level='error')
            else:
                raise cherrypy.HTTPRedirect(url_for(self.model))
