# udb, A web interface to manage IT network
# Copyright (C) 2022-2026 IKUS Software inc.
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

import cherrypy
from cherrypy_foundation.flash import flash
from cherrypy_foundation.form import CherryForm
from cherrypy_foundation.tools.i18n import gettext_lazy as _
from wtforms.fields import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import InputRequired, Length


class LoginForm(CherryForm):
    login = StringField(
        _('Username'),
        default=lambda: cherrypy.tools.auth.get_user_key() or "",
        validators=[
            InputRequired(),
            Length(max=256, message=_('Username too long.')),
        ],
        render_kw={
            "placeholder": _('Username'),
            "autocorrect": "off",
            "autocapitalize": "none",
            "autocomplete": "off",
            "autofocus": "autofocus",
        },
    )
    password = PasswordField(
        _('Password'),
        validators=[
            InputRequired(),
            Length(max=256, message=_('Password too long.')),
        ],
        render_kw={"placeholder": _("Password")},
    )
    persistent = BooleanField(
        _('Remember me'),
        default=lambda: cherrypy.tools.sessions_timeout.is_persistent(),
        render_kw={'container_class': 'col-sm-6'},
    )
    submit = SubmitField(
        _('Sign in'),
        render_kw={"class": "btn-primary float-end", 'container_class': 'col-sm-6'},
    )


class LoginPage:
    """
    This page is used by the authentication to display enter a user/pass.
    """

    @cherrypy.expose
    @cherrypy.tools.allow(methods=['GET', 'POST'])
    @cherrypy.tools.auth_mfa(on=False)
    @cherrypy.tools.jinja2(template='login.html')
    @cherrypy.tools.ratelimit(methods=['POST'])
    def index(self, **kwargs):

        # Redirect user to dashboard page if already login
        if getattr(cherrypy.request, 'login', False):
            raise cherrypy.HTTPRedirect('/')

        #  When data is submited, validate credentials.
        form = LoginForm(data=cherrypy.request.params)
        if form.validate_on_submit():
            userobj = cherrypy.tools.auth.login_with_credentials(form.login.data, form.password.data)
            if userobj:
                cherrypy.tools.sessions_timeout.set_persistent(form.persistent.data)
                raise cherrypy.tools.auth.redirect_to_original_url()
            else:
                flash(_('Invalid credentials'))
        elif form.error_message:
            flash(form.error_message)

        # Re-encode the redirect for display in HTML
        params = {'form': form}

        return params


class LogoutPage:

    @cherrypy.expose()
    @cherrypy.tools.allow(methods=['POST'])
    @cherrypy.tools.auth(on=False)
    @cherrypy.tools.auth_mfa(on=False)
    @cherrypy.tools.ratelimit(methods=['POST'])
    def default(self, **kwargs):
        """
        Logout user
        """
        cherrypy.tools.auth.clear_session()
        raise cherrypy.HTTPRedirect('/')
