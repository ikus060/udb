# -*- coding: utf-8 -*-
# udb, A web interface to manage IT network
# Copyright (C) 2023 IKUS Software inc.
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
import logging

import cherrypy
from wtforms.fields import BooleanField, StringField, SubmitField
from wtforms.validators import ValidationError

from udb.controller import flash
from udb.controller.form import CherryForm
from udb.tools.auth_form import LOGIN_PERSISTENT
from udb.tools.i18n import gettext_lazy as _

# Define the logger
logger = logging.getLogger(__name__)


class MfaForm(CherryForm):
    code = StringField(
        _('Verification code'),
        # Trim spaces
        filters=[lambda v: v.strip() if v else v],
        render_kw={
            "class": "form-control-lg",
            "placeholder": _('Enter verification code here'),
            "autocomplete": "off",
            "autocorrect": "off",
            "autofocus": "autofocus",
        },
    )
    persistent = BooleanField(
        _('Remember me'), default=lambda: cherrypy.session.get(LOGIN_PERSISTENT, False), render_kw={'width': '1/2'}
    )
    submit = SubmitField(
        _('Sign in'),
        render_kw={"class": "btn-primary float-end", 'width': '1/2'},
    )
    resend_code = SubmitField(
        _('Resend code to my email'),
        render_kw={"class": "btn-link", "style": "padding-left:0"},
    )

    def validate_code(self, field):
        # Code is required when submit.
        if self.submit.data:
            if not self.code.data:
                raise ValidationError(_('Invalid verification code.'))
            # Validate verification code.
            if not cherrypy.tools.auth_mfa.verify_code(code=self.code.data, persistent=self.persistent.data):
                raise ValidationError(_('Invalid verification code.'))

    def validate(self, extra_validators=None):
        if not (self.submit.data or self.resend_code.data):
            raise ValidationError(_('Invalid operation'))
        return super().validate()


class MfaPage:
    @cherrypy.expose()
    @cherrypy.tools.ratelimit(methods=['POST'])
    @cherrypy.tools.jinja2(template='mfa.html')
    def index(self, **kwargs):
        form = MfaForm()

        # Validate MFA
        if form.is_submitted():
            if form.validate():
                if form.submit.data:
                    cherrypy.tools.auth_mfa.redirect_to_original_url()
                elif form.resend_code.data:
                    self.send_code()
        if cherrypy.tools.auth_mfa.is_code_expired():
            # Send verification code if previous code expired.
            self.send_code()
        params = {
            'form': form,
        }
        # Add welcome message to params. Try to load translated message.
        return params

    def send_code(self):
        # Send verification code by email
        userobj = cherrypy.serving.request.currentuser
        if not userobj.email:
            flash(
                _(
                    "Multi-factor authentication is enabled for your account, but your account does not have a valid email address to send the verification code to. Check your account settings with your administrator."
                )
            )
            return
        code = cherrypy.tools.auth_mfa.generate_code()
        cherrypy.notification.queue_mail(
            userobj,
            template="email_verification_code.html",
            code=code,
            user=userobj,
        )
        flash(_("A new verification code has been sent to your email."))
