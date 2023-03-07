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
from wtforms.fields import BooleanField, PasswordField, StringField
from wtforms.fields.simple import HiddenField
from wtforms.validators import InputRequired, Length, Regexp

from udb.config import Option
from udb.controller import flash
from udb.controller.form import CherryForm
from udb.tools.auth_form import LOGIN_PERSISTENT, SESSION_KEY
from udb.tools.i18n import gettext_lazy as _


class LoginForm(CherryForm):
    username = StringField(
        _('Username'),
        default=lambda: cherrypy.session.get(SESSION_KEY, None),
        validators=[
            InputRequired(),
            Length(max=256),
        ],
        render_kw={"placeholder": _("Enter a valid email address")},
    )
    password = PasswordField(
        _('Password'),
        validators=[
            InputRequired(),
            Length(max=256),
        ],
        render_kw={"placeholder": _("Enter password")},
    )
    persistent = BooleanField(
        _('Remember me'),
        default=lambda: cherrypy.session.get(LOGIN_PERSISTENT, False),
    )
    redirect = HiddenField(default='/', validators=[Regexp('^/', message=_('invalid redirect url'))])


class LoginPage:
    """
    This page is used by the authentication to display enter a user/pass.
    """

    _welcome_msg = Option("welcome_msg")

    @cherrypy.expose
    @cherrypy.tools.jinja2(template='login.html')
    @cherrypy.tools.ratelimit(methods=['POST'])
    def index(self, **kwargs):

        #  When data is submited, validate credentials.
        form = LoginForm(data=cherrypy.request.params)
        if form.validate_on_submit():
            results = [r for r in cherrypy.engine.publish('login', form.username.data, form.password.data) if r]
            if len(results) > 0 and results[0]:
                cherrypy.tools.auth_form.login(username=results[0].username, persistent=form.persistent.data)
                cherrypy.tools.auth_form.redirect_to_original_url()
            else:
                flash(_('Invalid crentials'))
        elif form.error_message:
            flash(form.error_message)

        # Re-encode the redirect for display in HTML
        params = {'form': form}

        # Add welcome message to params. Try to load translated message.
        if self._welcome_msg:
            params["welcome_msg"] = self._welcome_msg.get('')
            if hasattr(cherrypy.response, 'i18n'):
                locale = cherrypy.response.i18n.locale.language
                params["welcome_msg"] = self._welcome_msg.get(locale, params["welcome_msg"])

        return params
