# udb, A web interface to manage IT network
# Copyright (C) 2025 IKUS Software inc.
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
from cherrypy_foundation.tools.i18n import gettext as _
from cherrypy_foundation.widgets import SideBySideMultiSelect
from markupsafe import Markup
from wtforms.fields import SelectField, SelectMultipleField


class JinjaWidget:
    """
    Create field widget from Jinja2 templates.
    """

    filename = None

    def __init__(self, **options):
        self.options = options

    def __call__(self, field, **kwargs):
        env = cherrypy.request.config.get('tools.jinja2.env')
        kwargs = dict(self.options, **kwargs)
        # Support JinjaX
        if self.filename.endswith('.jinja'):
            catalog = env.globals['catalog']
            return catalog.irender(self.filename[0:-6], field=field, **kwargs)
        else:
            tmpl = env.get_template(self.filename)
            return Markup(tmpl.render(field=field, **kwargs))


# Widget that could be used with FieldList
class TableWidget(JinjaWidget):
    filename = 'widgets/TableWidget.html'


class SubnetTableWidget(JinjaWidget):
    filename = 'SubnetTableWidget.jinja'


class SelectMultipleObjectField(SelectMultipleField):
    """
    Field to select one or more sqlalchemy object.
    """

    widget = SideBySideMultiSelect()

    def __init__(self, label=None, validators=None, object_cls=None, object_query=None, **kwargs):
        assert object_cls
        assert object_query is None or hasattr(object_query, '__call__')
        super().__init__(label, validators, coerce=self.db_obj, choices=None, **kwargs)
        self.object_cls = object_cls
        self.object_query = object_query

    def _summary_with_status(self, obj):
        """
        Return a summary with a status.
        """
        if obj.estatus == self.object_cls.STATUS_ENABLED:
            return obj.summary
        elif obj.estatus == self.object_cls.STATUS_DISABLED:
            return obj.summary + ' [%s]' % _('Disabled')
        return obj.summary + ' [%s]' % _('Deleted')

    @property
    def choices(self):
        """
        Replace default implementation by returning the list of objects.
        Hide deleted record
        """
        entries = [
            (obj.id, self._summary_with_status(obj))
            for obj in self._query().all()
            if obj.estatus != self.object_cls.STATUS_DELETED or (self.data and obj.id in self.data)
        ]
        return entries

    @choices.setter
    def choices(self, new_choices):
        # Disallow modification of choices
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
        values = self.object_cls.query.filter(self.object_cls.id.in_(self.data)).all()
        setattr(obj, name, values)

    def _query(self):
        """
        Build query of object to be listed by the Field.
        """
        q = self.object_cls.query.with_entities(
            self.object_cls.id, self.object_cls.summary, self.object_cls.estatus
        ).order_by(self.object_cls.summary)
        if self.object_query:
            assert hasattr(self.object_query, '__call__'), "object_query should be callable"
            q = self.object_query()
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

    def _summary_with_status(self, obj):
        """
        Return a summary with a status.
        """
        if obj.estatus == self.object_cls.STATUS_ENABLED:
            return obj.summary
        elif obj.estatus == self.object_cls.STATUS_DISABLED:
            return obj.summary + ' [%s]' % _('Disabled')
        return obj.summary + ' [%s]' % _('Deleted')

    @property
    def choices(self):
        """
        Replace default implementation by returning the list of objects.
        """
        entries = [
            (obj.id, self._summary_with_status(obj))
            for obj in self._query().all()
            if obj.estatus != self.object_cls.STATUS_DELETED or obj.id == self.data
        ]
        # Add a "null" option if the field is optional
        if 'required' not in self.flags:
            entries.insert(0, (None, _("-")))
        return entries

    @choices.setter
    def choices(self, new_choices):
        # Disallow modification of choices
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
            # Then fetch the object using another query.
            value = self.object_cls.query.filter(self.object_cls.id == self.data).first()
            setattr(obj, name[:-3], value)
        else:
            super().populate_obj(obj, name)

    def _query(self):
        """
        Build query of object to be listed by the Field.
        """
        q = self.object_cls.query.with_entities(
            self.object_cls.id, self.object_cls.summary, self.object_cls.estatus
        ).order_by(self.object_cls.summary)
        if self.object_query:
            assert hasattr(self.object_query, '__call__'), "object_query should be callable"
            q = self.object_query()
        return q
