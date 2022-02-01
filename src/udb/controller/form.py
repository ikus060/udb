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
from markupsafe import Markup, escape
from udb.tools.i18n import gettext as _
from wtforms.fields import SelectField, SelectMultipleField
from wtforms.form import Form

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


def _get_bs_field_class(field):
    """
    Return a list of class for the given field.
    """
    cls = []
    if type(field.widget).__name__ == 'Select':
        cls.append('form-select')
    elif type(field.widget).__name__ in ['TextInput', 'TextArea', 'PasswordInput']:
        cls.append('form-control')

    # Add is-valid or is-invalid accordingly.
    if field.errors:
        cls.append('is-invalid')
    return ' '.join(cls)


class CherryForm(Form):
    """
    Custom implementation of WTForm for cherrypy to support kwargs parms.

    If ``formdata`` is not specified, this will use cherrypy.request.params
    Explicitly pass ``formdata=None`` to prevent this.
    """

    def __init__(self, **kwargs):
        super().__init__(formdata=_AUTO if self.is_submitted() else None, **kwargs)

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

    def add_error(self, field, message):
        """
        Explicitly add an error to this form.
        """
        self.errors[field].append(message)

    def __html__(self):
        """
        Return a HTML representation of the form. For more powerful rendering, see the __call__() method.
        """
        return self()

    def __call__(self, floating=False):
        """
        Generate an HTML representation of this form using bootstrap 5.
        """

        def generator():
            for id, field in self._fields.items():
                if field.type == 'HiddenField':
                    yield field()
                else:
                    # Get proper bootstrap class for the widget
                    cur_field_class = _get_bs_field_class(field)
                    cur_label_class = 'form-label' + \
                        (' is-invalid' if field.errors else '')

                    # Check if form-floating is enabled and supported for the given field.
                    is_form_floating = floating and type(field.widget).__name__ not in [
                        'SelectMultiCheckbox']
                    cur_div_class = 'form-floating mb-2' if is_form_floating else 'mb-3'

                    # Create html layout accordingly.
                    yield Markup('<div class="%s">' % cur_div_class)
                    if is_form_floating:
                        # For floating element we need to place the label after the input element
                        yield field(**{'class': cur_field_class})
                        yield field.label(**{'class': cur_label_class})
                    else:
                        yield field.label(**{'class': cur_label_class})
                        yield field(**{'class': cur_field_class})

                    # Append error messages to the form.
                    for error in field.errors:
                        yield Markup('<div class="%s">%s</div>' % ('invalid-feedback', escape(error)))
                    yield Markup('</div>')
        return Markup('').join(list(generator()))


class JinjaWidget():
    """
    Create field widget from Jinja2 templates.
    """
    filename = None

    def __init__(self, **options):
        self.options = options

    def __call__(self, field, **kwargs):
        env = cherrypy.request.config.get('tools.jinja2.env')
        tmpl = env.get_template(self.filename)
        kwargs = dict(self.options, **kwargs)
        return Markup(tmpl.render(field=field, **kwargs))


# Widget that could be used with SelectMultipleObjectField.
class SelectMultiCheckbox(JinjaWidget):
    filename = 'widgets/SelectMultiCheckbox.html'


# Widget that could be used with FieldList
class TableWidget(JinjaWidget):
    filename = 'widgets/TableWidget.html'


class SelectMultipleObjectField(SelectMultipleField):
    """
    Field to select one or more sqlalchemy object.
    """

    def __init__(self, label=None, validators=None, object_cls=None, **kwargs):
        assert object_cls
        super().__init__(label, validators, coerce=self.db_obj, choices=None, **kwargs)
        self.object_cls = object_cls

    @property
    def choices(self):
        """
        Replace default implementation by returning the list of objects.
        """
        return [(obj.id, str(obj)) for obj in self.object_cls.query.all()]

    @choices.setter
    def choices(self, new_choices):
        pass

    def db_obj(self, value):
        if value is None or value == 'None':
            return []
        elif isinstance(value, self.object_cls):
            return value.id
        return int(value)

    def populate_obj(self, obj, name):
        """
        Assign object value.
        """
        values = self.object_cls.query.filter(
            self.object_cls.id.in_(self.data)).all()
        setattr(obj, name, values)


class SelectObjectField(SelectField):
    """
    Field to select a single sqlalchemy object. e.g.: select a User
    """

    def __init__(self, label=None, validators=None, object_cls=None, **kwargs):
        assert object_cls
        super().__init__(label, validators, coerce=self.db_obj, choices=None, **kwargs)
        self.object_cls = object_cls

    @property
    def choices(self):
        """
        Replace default implementation by returning the list of objects.
        """
        # TODO Avoid showing deleted records.
        entries = [(obj.id, str(obj)) for obj in self.object_cls.query.all()]
        if self.data is None:
            entries.insert(0, (None, _("Not assigned")))
        return entries

    @choices.setter
    def choices(self, new_choices):
        pass

    def db_obj(self, value):
        if value is None or value == 'None':
            return None
        elif isinstance(value, self.object_cls):
            return value
        return int(value)

    def populate_obj(self, obj, name):
        """
        Assign object value.
        """
        value = None
        if self.data:
            value = self.object_cls.query.filter_by(id=self.data).first()
        setattr(obj, name, value)
