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
from wtforms.fields import BooleanField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length

from udb.controller import url_for
from udb.core.model import Rule, User, all_models
from udb.tools.i18n import gettext_lazy as _

from .common_page import CommonApi, CommonPage
from .form import CherryForm, SelectObjectField, SwitchWidget


class RuleForm(CherryForm):
    object_cls = Rule

    name = StringField(
        _('Rule Identifier'),
        validators=[DataRequired(), Length(max=256)],
        render_kw={
            "placeholder": _("Rule Identifier"),
            "autofocus": True,
            'width': '1/2',
        },
    )

    severity = BooleanField(
        _('Enforced'),
        widget=SwitchWidget(),
        render_kw={
            'width': '1/4',
        },
        description=_('Enforced rule prevent record from being saved.'),
    )

    builtin = BooleanField(
        _('Built-in'),
        widget=SwitchWidget(),
        render_kw={
            'width': '1/4',
            'readonly': True,
            'disabled': True,
        },
        description=_(
            "Built-in rules are predefined, unmodifiable constraints integral to the application's functionality."
        ),
    )

    description = StringField(
        _('Description'),
        validators=[DataRequired(), Length(max=256)],
        render_kw={"placeholder": _("Description of the rule.")},
    )

    model_name = SelectField(
        _('Data Type'),
        validators=[
            DataRequired(),
            Length(max=256),
        ],
    )

    statement = TextAreaField(
        _('SQL Statement'),
        validators=[DataRequired(), Length(max=10485760)],
        render_kw={
            "placeholder": _("SQL Statement returning list of invalid records."),
            "rows": 10,
        },
        description=_(
            'The SQL statement should return a row for each invalid record. The columns should be labeled: id, name.'
        ),
    )

    notes = TextAreaField(
        _('Notes'),
        default='',
        validators=[Length(max=256)],
        render_kw={"placeholder": _("Enter details information about this Rule")},
    )

    owner_id = SelectObjectField(
        _('Owner'),
        object_cls=User,
        default=lambda: cherrypy.serving.request.currentuser.id,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Load list of model
        self.model_name.choices = [(cls.__tablename__, cls.__tablename__) for cls in all_models]
        # Make fields readonly for builtin
        if self.builtin.data:
            for field in self:
                field.render_kw = field.render_kw.copy() if field.render_kw else {}
                field.render_kw['disabled'] = True
                field.render_kw['readonly'] = True

    def populate_obj(self, obj):
        super().populate_obj(obj)
        # convert severity from bool to int for database
        obj.severity = int(self.severity.data)


class RulePage(CommonPage):
    def __init__(self):
        super().__init__(
            Rule,
            RuleForm,
            edit_perm=User.PERM_RULE_EDIT,
            new_perm=User.PERM_RULE_EDIT,
        )

    @cherrypy.expose
    @cherrypy.tools.jinja2(template=['{model_name}/edit.html', 'common/edit.html'])
    def edit(self, key, **kwargs):
        """
        Remove "status" on unique and check constraints.
        """
        values = super().edit(key, **kwargs)
        obj = values['obj']
        if obj.type in [Rule.TYPE_CHECK, Rule.TYPE_UNIQUE]:
            values['has_status'] = False
        return values

    def _list_query(self):
        return Rule.session.query(
            Rule.id,
            Rule.estatus,
            Rule.name,
            Rule.model_name,
            Rule.description,
            Rule.severity,
            Rule.builtin,
            Rule.type,
            User.summary.label('owner'),
        ).outerjoin(Rule.owner)

    @cherrypy.expose()
    @cherrypy.tools.json_out()
    def linter_json(self, **kwargs):
        """
        Execute the linter and return each row with a link to the problematic record.
        """
        return {
            'data': [
                (
                    row.description,
                    row.id,
                    row.severity,
                    row.model_name,
                    row.name,
                    url_for(row.model_name, row.id, 'edit'),
                )
                for row in Rule.verify()
            ]
        }


class RuleApi(CommonApi):
    def __init__(self):
        super().__init__(
            Rule,
            list_perm=User.PERM_NETWORK_LIST,
            edit_perm=User.PERM_RULE_EDIT,
            new_perm=User.PERM_RULE_EDIT,
        )
