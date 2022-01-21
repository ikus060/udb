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
from udb.config import Option
from udb.controller import flash
from udb.controller.wtf import CherryForm
from udb.core.model import User, UserLoginException
from udb.tools.auth_form import SESSION_KEY
from udb.tools.i18n import gettext as _
from wtforms.fields import PasswordField, StringField
from wtforms.fields.simple import HiddenField
from wtforms.validators import InputRequired


class LoginForm(CherryForm):
    username = StringField(
        _('Username'),
        validators=[InputRequired()],
        render_kw={"placeholder": _("Enter a valid email address")})
    password = PasswordField(
        _('Password'),
        validators=[InputRequired()],
        render_kw={"placeholder": _("Enter password")})
    redirect = HiddenField(default='/')


class LoginPage():
    """
    This page is used by the authentication to display enter a user/pass.
    """

    _welcome_msg = Option("welcome_msg")

    @cherrypy.expose
    @cherrypy.tools.auth_form(on=False)
    @cherrypy.tools.jinja2(template='login.html')
    def index(self, **kwargs):
        # If user is already login, redirect him
        if cherrypy.session.get(SESSION_KEY, None):
            raise cherrypy.HTTPRedirect('/')

        #  When data is submited, validate credentials.
        form = LoginForm(data=cherrypy.request.params)
        if form.validate_on_submit():
            try:
                username = User.login(
                    form.username.data, form.password.data)
                assert username
                cherrypy.session[SESSION_KEY] = username
                raise cherrypy.HTTPRedirect(form.redirect.data or '/')
            except UserLoginException:
                flash(_('Invalid crentials'))

        # Re-encode the redirect for display in HTML
        params = {
            'form': form
        }

        # Add welcome message to params. Try to load translated message.
        if self._welcome_msg:
            params["welcome_msg"] = self._welcome_msg.get('')
            if hasattr(cherrypy.response, 'i18n'):
                locale = cherrypy.response.i18n.locale.language
                params["welcome_msg"] = self._welcome_msg.get(
                    locale, params["welcome_msg"])

        return params
