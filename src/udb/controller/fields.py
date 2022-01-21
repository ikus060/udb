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
from udb.tools.i18n import gettext as _
from wtforms.fields.core import SelectField, SelectMultipleField

from wtforms.widgets import html_params
from markupsafe import Markup, escape


class SelectMultiCheckbox():

    def __call__(self, field, **kwargs):

        def generator():
            kwargs.setdefault('type', 'checkbox')
            field_id = kwargs.pop('id', field.id)
            yield Markup('<div %s>' % html_params(id=field_id))
            for value, label, checked in field.iter_choices():
                choice_id = '%s-%s' % (field_id, value)
                options = dict(kwargs, name=field.name,
                               value=value, id=choice_id)
                if checked:
                    options['checked'] = 'checked'
                yield Markup('<div class="form-check">')
                yield Markup('<input %s /> ' % html_params(**options))
                yield Markup('<label for="%s">%s</label>' % (field_id, escape(label)))
                yield Markup('</div>')
            yield Markup('</div>')

        return Markup('').join(list(generator()))


class SelectMultipleObjectField(SelectMultipleField):
    """
    Field to select multiple object.
    """

    def __init__(self, label=None, validators=None, object_cls=None, **kwargs):
        assert object_cls
        super().__init__(label, validators, coerce=self.db_obj,
                         choices=None, validate_choice=True, **kwargs)
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

    @property
    def display(self):
        """
        Return a human readable display of the value.
        """
        if self.data:
            values = self.object_cls.query.filter(
                self.object_cls.id.in_(self.data)).all()
            return Markup(' ').join([
                Markup(
                    '<a href="%s"><span class="badge rounded-pill bg-secondary">%s</span></a>' % (v.url(), v))
                for v in values])
        return '-'


class SelectObjectField(SelectField):
    """
    Field to select an object.
    """

    def __init__(self, label=None, validators=None, object_cls=None, **kwargs):
        assert object_cls
        super().__init__(label, validators, coerce=self.db_obj,
                         choices=None, validate_choice=True, **kwargs)
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

    @property
    def display(self):
        """
        Return a human readable display of the value.
        """
        return ' '.join([c[1] for c in self.choices if c[0] == self.data])
