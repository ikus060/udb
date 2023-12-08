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
from wtforms.fields import StringField, SubmitField
from wtforms.validators import ValidationError
from wtforms.widgets import HiddenInput

from udb.controller import flash
from udb.controller.form import CherryForm
from udb.core.model import User
from udb.tools.i18n import gettext_lazy as _


class MfaToggleForm(CherryForm):
    code = StringField(
        _('Verification code'),
        # Trim spaces
        filters=[lambda v: v.strip() if v else v],
        render_kw={
            "placeholder": _('Enter verification code here'),
            "autocomplete": "off",
            "autocorrect": "off",
            "autofocus": "autofocus",
        },
    )
    resend_code = SubmitField(
        _('Resend code to my email'),
        render_kw={"class": "btn-link", 'width': '1/2', 'style': 'padding-left:0;'},
    )
    enable_mfa = SubmitField(_('Enable'), render_kw={"class": "btn-success float-end", 'width': '1/2'})
    disable_mfa = SubmitField(_('Disable'), render_kw={"class": "btn-warning float-end", 'width': '1/2'})

    def __init__(self, obj, **kwargs):
        assert obj
        super().__init__(obj=obj, **kwargs)
        # Keep only one of the enable or disable button
        if obj.mfa:
            self.enable_mfa.widget = HiddenInput()
            self.enable_mfa.data = ''
        else:
            self.disable_mfa.widget = HiddenInput()
            self.disable_mfa.data = ''

    def populate_obj(self, userobj):
        # Enable or disable MFA only when a code is provided.
        try:
            if self.enable_mfa.data:
                userobj.mfa = User.MFA_ENABLED
                userobj.commit()
                flash(_("Two-Factor authentication enabled successfully."), level='success')
            elif self.disable_mfa.data:
                userobj.mfa = User.MFA_DISABLED
                userobj.commit()
                flash(_("Two-Factor authentication disabled successfully."), level='success')
            return True
        except Exception as e:
            userobj.rollback()
            flash(str(e), level='warning')
            return False

    def validate_code(self, field):
        # Code is required for enable_mfa and disable_mfa
        if self.enable_mfa.data or self.disable_mfa.data:
            if not self.code.data:
                raise ValidationError(_("Enter the verification code to continue."))
            # Validate code
            if not cherrypy.tools.auth_mfa.verify_code(self.code.data, False):
                raise ValidationError(_("Invalid verification code."))

    def validate(self, extra_validators=None):
        if not (self.enable_mfa.data or self.disable_mfa.data or self.resend_code.data):
            raise ValidationError(_('Invalid operation'))
        return super().validate()


class ProfileMfaPage:
    @cherrypy.expose
    @cherrypy.tools.ratelimit(methods=['POST'])
    @cherrypy.tools.jinja2(template=['profile_mfa.html'])
    def default(self, **kwargs):
        currentuser = cherrypy.serving.request.currentuser
        form = MfaToggleForm(obj=currentuser)
        if form.is_submitted():
            if form.validate():
                if form.resend_code.data:
                    self.send_code()
                    form = MfaToggleForm(obj=currentuser)
                elif form.enable_mfa.data or form.disable_mfa.data:
                    if form.populate_obj(currentuser):
                        raise cherrypy.HTTPRedirect("/profile/")
            # Send verification code if previous code expired.
            elif cherrypy.tools.auth_mfa.is_code_expired():
                self.send_code()
                form = MfaToggleForm(obj=currentuser)
        params = {
            'form': form,
        }
        return params

    def send_code(self):
        currentuser = cherrypy.serving.request.currentuser
        if not currentuser.email:
            flash(_("To continue, you must set up an email address for your account."), level='warning')
            return
        code = cherrypy.tools.auth_mfa.generate_code()
        cherrypy.notification.queue_mail(
            currentuser,
            template="email_verification_code.html",
            code=code,
            user=currentuser,
        )
        flash(_("A new verification code has been sent to your email."))
