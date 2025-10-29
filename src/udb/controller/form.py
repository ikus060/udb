# Cherrypy Form
# Copyright (C) 2020-2025 IKUS Software
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
from markupsafe import Markup
from wtforms.form import Form


class _ProxyFormdata:
    """
    Custom class to proxy default form data into WTForm from cherrypy variables.
    """

    def __contains__(self, key):
        return key in cherrypy.request.params

    def getlist(self, key):
        # Default to use cherrypy params.
        params = cherrypy.request.params
        if key in params:
            if isinstance(params[key], list):
                return params[key]
            else:
                return [params[key]]
        # Return default empty list.
        return []

    def __iter__(self):
        return iter(cherrypy.request.params)


_AUTO = _ProxyFormdata()


class CherryForm(Form):
    """
    Custom implementation of WTForm for cherrypy to support kwargs parms.

    If ``formdata`` is not specified, this will use cherrypy.request.params
    Explicitly pass ``formdata=None`` to prevent this.
    """

    def __init__(self, **kwargs):
        # Seamlessly support Json input if available.
        if 'json' in kwargs and kwargs.pop('json'):
            cherrypy.request.params = getattr(cherrypy.request, 'json', cherrypy.request.params)
        # Support explicit formdata
        if 'formdata' in kwargs:
            formdata = kwargs.pop('formdata')
        else:
            formdata = _AUTO if CherryForm.is_submitted(self) else None
        super().__init__(formdata=formdata, **kwargs)

    def is_submitted(self):
        """
        Consider the form submitted if there is an active request and
        the method is ``POST``.
        """
        return cherrypy.request.method == 'POST'

    def strict_validate(self):
        """
        Special validation to verify if all the field submited exists in this form.
        Raise an error if some fields are unknown.
        """
        form_errors = self.form_errors if hasattr(self, 'form_errors') else self.errors.setdefault(None, [])
        for key in cherrypy.request.params.keys():
            if key not in self:
                form_errors.append("unsuported field: %s" % key)
                return False
        return self.validate()

    def validate_on_submit(self):
        """
        Call `validate` only if the form is submitted.
        This is a shortcut for ``form.is_submitted() and form.validate()``.
        """
        return self.is_submitted() and self.validate()

    @property
    def error_message(self):
        """
        Return all error message in a single string.
        """
        if self.errors:
            msg = Markup("")
            for field, messages in self.errors.items():
                if msg:
                    msg += Markup('<br/>')
                # Field name
                if field in self:
                    msg += "%s: " % self[field].label.text
                elif field:
                    msg += "%s: " % field
                for m in messages:
                    msg += m
            return msg

    def populate_obj(self, obj):
        """
        Override default implementation to take acount of readonly fields.
        """
        for name, field in self._fields.items():
            if field.render_kw and field.render_kw.get('readonly'):
                continue
            field.populate_obj(obj, name)
