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
from markupsafe import Markup
from wtforms.fields import SelectField, SelectMultipleField
from wtforms.form import Form

from udb.tools.i18n import gettext as _


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

    class Meta:
        def render_field(self, field, render_kw):
            # Merge the two render_kw
            render_kw = render_kw.copy()
            other_kw = getattr(field, "render_kw", None)
            if other_kw:
                other_kw = other_kw.copy()
                for k, v in render_kw.items():
                    if k in ['class', 'class_']:
                        other_kw['class'] = other_kw.get('class', '') + ' ' + render_kw[k]
                    else:
                        other_kw[k] = render_kw[k]
                render_kw = other_kw
            env = cherrypy.request.config.get('tools.jinja2.env')
            tmpl = env.get_template('components/field.html')
            return Markup(tmpl.render(field=field, render_kw=render_kw))

    def __init__(self, **kwargs):
        super().__init__(formdata=_AUTO if self.is_submitted() else None, **kwargs)

    def is_submitted(self):
        """
        Consider the form submitted if there is an active request and
        the method is ``POST``.
        """
        return cherrypy.request.method == 'POST'

    def validate_on_submit(self):
        """
        Call `validate` only if the form is submitted.
        This is a shortcut for ``form.is_submitted() and form.validate()``.
        """
        return self.is_submitted() and self.validate()

    @property
    def error_message(self):
        if self.errors:
            return ' '.join(
                ['%s: %s' % (field, ', '.join([str(m) for m in messages])) for field, messages in self.errors.items()]
            )

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

    def __call__(self, **kwargs):
        env = cherrypy.request.config.get('tools.jinja2.env')
        tmpl = env.get_template('components/form.html')
        return Markup(tmpl.render(form=self, **kwargs))


class JinjaWidget:
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


class DualListWidget(JinjaWidget):
    filename = 'widgets/DualListWidget.html'


# Widget that could be used with SelectMultipleObjectField.
class SelectMultiCheckbox(JinjaWidget):
    filename = 'widgets/SelectMultiCheckbox.html'


# Widget that could be used with FieldList
class TableWidget(JinjaWidget):
    filename = 'widgets/TableWidget.html'


class SubnetTableWidget(JinjaWidget):
    filename = 'widgets/SubnetTableWidget.html'


class SelectMultipleObjectField(SelectMultipleField):
    """
    Field to select one or more sqlalchemy object.
    """

    def __init__(self, label=None, validators=None, object_cls=None, object_query=None, **kwargs):
        assert object_cls
        assert object_query is None or hasattr(object_query, '__call__')
        super().__init__(label, validators, coerce=self.db_obj, choices=None, **kwargs)
        self.object_cls = object_cls
        self.object_query = object_query

    @property
    def choices(self):
        """
        Replace default implementation by returning the list of objects.
        """
        return [(obj.id, str(obj)) for obj in self._query().all()]

    @choices.setter
    def choices(self, new_choices):
        pass

    def db_obj(self, value):
        if value is None or value == 'None':
            return []
        elif hasattr(value, 'id'):
            return value.id
        return int(value)

    def populate_obj(self, obj, name):
        """
        Assign object value.
        """
        values = self._query().filter(self.object_cls.id.in_(self.data)).all()
        setattr(obj, name, values)

    def _query(self):
        q = self.object_cls.query
        if self.object_query:
            q = self.object_query(q)
        return q


class SelectObjectField(SelectField):
    """
    Field to select a single sqlalchemy object. e.g.: select a User
    """

    def __init__(self, label=None, validators=None, object_cls=None, object_query=None, **kwargs):
        assert object_cls
        assert object_query is None or hasattr(object_query, '__call__')
        super().__init__(label, validators, coerce=self.obj_id, choices=None, **kwargs)
        self.object_cls = object_cls
        self.object_query = object_query

    @property
    def choices(self):
        """
        Replace default implementation by returning the list of objects.
        """
        # TODO Avoid showing deleted records.
        entries = [(obj.id, str(obj)) for obj in self._query().all()]
        if 'required' not in self.flags:
            entries.insert(0, (None, _("-")))
        return entries

    @choices.setter
    def choices(self, new_choices):
        pass

    def obj_id(self, value):
        if value is None or value == 'None':
            return None
        elif isinstance(value, self.object_cls):
            return value.id
        return int(value)

    def populate_obj(self, obj, name):
        """
        Let populate the object in a special way to help sqlalchemy
        history to show object change instead of object_id change.
        """
        # If the attribute could be assigned as an object, let update the object.
        if name.endswith('_id') and hasattr(obj, name[:-3]):
            value = self._query().filter_by(id=self.data).first()
            setattr(obj, name[:-3], value)
        else:
            super().populate_obj(obj, name)

    def _query(self):
        q = self.object_cls.query
        if self.object_query:
            q = self.object_query(q)
        return q


class StringFieldSetWidget(JinjaWidget):
    filename = 'widgets/StringFieldSetWidget.html'
