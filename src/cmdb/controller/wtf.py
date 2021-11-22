# -*- coding: utf-8 -*-
# cmdb, A web interface to manage IT network CMDB
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
from wtforms.form import Form
from markupsafe import Markup, escape

SUBMIT_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}


class _ProxyFormdata():
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


_AUTO = _ProxyFormdata()


class CherryForm(Form):
    """
    Custom implementation of WTForm for cherrypy to support kwargs parms.

    If ``formdata`` is not specified, this will use cherrypy.request.params
    Explicitly pass ``formdata=None`` to prevent this.
    """

    def __init__(self, formdata=_AUTO, **kwargs):
        super().__init__(formdata=formdata, **kwargs)

    def is_submitted(self):
        """
        Consider the form submitted if there is an active request and
        the method is ``POST``, ``PUT``, ``PATCH``, or ``DELETE``.
        """
        return cherrypy.request.method in SUBMIT_METHODS

    def validate_on_submit(self):
        """
        Call `validate` only if the form is submitted.
        This is a shortcut for ``form.is_submitted() and form.validate()``.
        """
        return self.is_submitted() and self.validate()

    @property
    def error_message(self):
        if self.errors:
            return ' '.join(['%s: %s' % (field, ', '.join(messages)) for field, messages in self.errors.items()])

    def __html__(self):
        """
        Return a HTML representation of the form. For more powerful rendering, see the __call__() method.
        """
        return self()

    def __call__(self, div_class='form-outline', label_class='form-label', field_class='form-control', error_class='invalid-feedback'):

        def generator():
            for id, field in self._fields.items():
                if field.type == 'HiddenField':
                    yield field(**{'class': field_class})
                else:
                    yield Markup('<div class="%s">' % escape(div_class))
                    yield field.label(**{'class': label_class})
                    yield field(**{'class': field_class})
                    for error in field.errors:
                        yield Markup('<div class="%s">%s</div>' % (escape(error_class), escape(error)))
                    yield Markup('</div>')
        return Markup('').join(list(generator()))
