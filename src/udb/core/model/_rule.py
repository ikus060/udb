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

import logging
from collections import namedtuple

import cherrypy
from sqlalchemy import Boolean, Column, SmallInteger, String, event, text
from sqlalchemy.ext.hybrid import hybrid_property

from udb.tools.i18n import gettext as _

from ._common import CommonMixin
from ._follower import FollowerMixin
from ._json import JsonMixin
from ._message import MessageMixin
from ._status import StatusMixing

logger = logging.getLogger(__name__)

Base = cherrypy.tools.db.get_base()

RuleDefinition = namedtuple('RuleDefinition', 'name,model_name,statement,description')

_rules = []


class Rule(CommonMixin, JsonMixin, MessageMixin, FollowerMixin, StatusMixing, Base):
    SEVERITY_SOFT = 0
    SEVERITY_ENFORCED = 1

    name = Column(String, nullable=False, unique=True)
    model_name = Column(String, nullable=False)
    statement = Column(String, nullable=False)
    description = Column(String, nullable=False)
    builtin = Column(Boolean, nullable=False, default=False)
    severity = Column(SmallInteger, nullable=False, default=SEVERITY_SOFT, server_default=str(SEVERITY_SOFT))

    @hybrid_property
    def summary(self):
        return self.name

    @classmethod
    def run_linter(cls, obj=None):
        """
        Run linter rule for all model.

        When `obj` is defined, return rule related to this specific model
        """
        assert obj is None or hasattr(obj.__class__, '__tablename__'), 'obj must be None or a model'
        # Query list of rules
        query_rules = Rule.query.filter(Rule.status == Rule.STATUS_ENABLED)
        if obj:
            model_name = obj.__class__.__tablename__
            query_rules = query_rules.filter(Rule.model_name == model_name)

        # Combine each rules into a single request using UNION ALL
        sql = ""
        for rule in query_rules.all():
            if sql:
                sql += ' UNION ALL '
            sql += rule._wrap_statement(obj)
        if not sql:
            return []
        return Rule.session.execute(text(sql)).all()

    def _wrap_statement(self, obj=None, new_statement=None):
        name = self.name.replace("'", "''")
        description = (self.description or '').replace("'", "''")
        severity = int(self.severity or Rule.SEVERITY_SOFT)
        model_name = self.model_name
        statement = new_statement or self.statement
        # Support 2 columns (id, summary) and 5 columns (id, name, other_id, other_model_name, other_name)
        if 'as other_id' not in statement.lower():
            sql = f"SELECT '{name}' as rule_name, '{description}' as description, {severity} as severity, id, '{model_name}' as model_name, name, 0 as other_id, NULL as other_model_name, NULL as other_name FROM ({statement}) as r{self.id}"
        else:
            sql = f"SELECT '{name}' as rule_name, '{description}' as description, {severity} as severity, id, '{model_name}' as model_name, name, other_id, other_model_name, other_name FROM ({statement}) as r{self.id}"
        # Add filter if an object is specified.
        if obj:
            sql += f" WHERE id = {obj.id}"
        return sql

    def _validate(self):
        """
        Used to validate the SQL statement before saving it into database to make sure it's a "valid" SQL.
        """

        # We need to make sure the statement is valid.
        # The best solution is to execute the statement.
        if not self.statement.lower().startswith('select '):
            raise ValueError('statement', _('your SQL statement should start with SELECT'))

        # While it's not bullet proof, check if we have `FROM model_name`
        if ('FROM %s' % self.model_name).lower() not in self.statement.lower():
            raise ValueError('statement', _('your SQL statement does not matches the selected data type'))

        # Execute the raw version to verify the column name
        try:
            fields = list(Rule.session.execute(text(self.statement)).keys())
            expected_fields = [
                'id',
                'name',
                'other_id',
                'other_model_name',
                'other_name',
            ]
            if fields != expected_fields[0:2] and fields != expected_fields:
                raise ValueError(
                    'statement',
                    _(
                        "your statement returned %s column(s) label as %s, but it's expected to return 2 or 5 columns labeled as: %s"
                    )
                    % (len(fields), ', '.join(fields), ', '.join(expected_fields)),
                )
        except Exception as e:
            raise ValueError('statement', str(e))

        # Execute the wrap version to validate SQL.
        try:
            sql = self._wrap_statement(new_statement=self.statement)
            Rule.session.execute(text(sql)).first()
        except Exception as e:
            raise ValueError('statement', str(e))


@event.listens_for(Rule, "before_update")
def before_update(mapper, connection, instance):
    instance._validate()


@event.listens_for(Rule, "before_insert")
def before_insert(mapper, connection, instance):
    instance._validate()


def rule(model, description):
    """
    Decorator to register linter rule.

    @rule('dnsrecord', 'human description')
    def name_of_rule():
        return select()...

    The query should return 3 columns or 6 columns:

    * id
    * name
    * other_id (optional)
    * other_model_name (optional)
    * other_name (optional)

    """

    def decorate(func):
        # Get rule name
        name = func.__name__
        assert name, 'rule require a valid name'
        # Get rule model_name
        model_name = getattr(model, '__tablename__', model)
        assert model_name and isinstance(model_name, str), 'rule required a valid model name'
        # Register the rule
        _rules.append(RuleDefinition(name, model_name, func, str(description)))
        return func

    return decorate


@event.listens_for(Base.metadata, 'after_create')
def create_update_rule(target, connection, **kw):

    # SQLAlchmey 1.4 Commit current transaction and open a new one.
    if getattr(connection, '_transaction', None):
        connection._transaction.commit()

    # For each soft rule register, make sure to create it in database
    for rule in _rules:
        obj = Rule.query.filter(Rule.name == rule[0]).first()
        if not obj:
            obj = Rule(name=rule.name)
        try:
            obj.description = rule.description
            obj.model_name = rule.model_name
            obj.statement = str(rule.statement().compile(connection.engine, compile_kwargs={"literal_binds": True}))
            obj.builtin = True
            obj.add()
            obj.flush()
        except Exception:
            logger.exception('fail to load rule in database')

    # Delete obsolete built-in rule
    Rule.query.filter(Rule.name.in_(['dns_ptr_record_mismatch'])).delete()

    # SQLAlchmey 1.4 Commit current transaction and open a new one.
    if getattr(connection, '_transaction', None):
        connection._transaction.commit()
