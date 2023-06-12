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
            'width': '2/3',
        },
    )

    builtin = BooleanField(
        _('Built In'),
        widget=SwitchWidget(),
        render_kw={
            'width': '1/3',
            'readonly': True,
            'disabled': True,
        },
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
            'The SQL statement should return a row for each invalid record. The columns should be labeled: id, model_name, summary, other_id, other_model_name, other_summary. '
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


class RulePage(CommonPage):
    def __init__(self):
        super().__init__(
            Rule,
            RuleForm,
            edit_perm=User.PERM_RULE_EDIT,
            new_perm=User.PERM_RULE_EDIT,
        )

    def _list_query(self):
        return Rule.session.query(
            Rule.id,
            Rule.status,
            Rule.name,
            Rule.model_name,
            Rule.description,
            Rule.builtin,
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
                list(row)
                + [
                    url_for(row.model_name, row.id, 'edit'),
                    row.other_id and url_for(row.other_model_name, row.other_id, 'edit'),
                ]
                for row in Rule.run_linter()
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
