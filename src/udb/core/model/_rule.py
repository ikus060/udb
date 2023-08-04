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

import cherrypy
from sqlalchemy import Boolean, Column, SmallInteger, String, event, text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import ddl

from udb.tools.i18n import gettext as _

from ._common import CommonMixin
from ._follower import FollowerMixin
from ._json import JsonMixin
from ._message import MessageMixin
from ._status import StatusMixing
from ._update import column_add, column_exists

logger = logging.getLogger(__name__)

Base = cherrypy.tools.db.get_base()


def _list_constraints():
    for table in Base.metadata.tables.values():
        for item in table.constraints:
            if item.name:
                yield item


def _list_indexes():
    for table in Base.metadata.tables.values():
        for item in table.indexes:

            if item.unique:
                yield item


class RuleError(Exception):
    def __init__(self, row):
        self.id = row.id
        self.name = row.name
        self.rule_name = row.rule_name
        self.description = row.description
        self.severity = row.severity
        self.field = row.field
        # Get callback function for built-in rule.
        rule_constraint = RuleConstraint._inventory.get(row.rule_name, None)
        if rule_constraint:
            self.related = rule_constraint.info.get('related', None)
        else:
            self.related = None


class RuleConstraint:
    """
    Create a builtin rule constraint.
    """

    _inventory = {}

    def __init__(self, name, model, statement, severity=None, info=None):
        assert name
        self.name = name
        model_name = getattr(model, '__tablename__', model)
        assert model_name and isinstance(model_name, str), 'rule required a valid model name'
        self.model_name = model_name
        self.statement = statement
        self.severity = severity or Rule.SEVERITY_SOFT
        self.info = info or {}
        # Register rule
        RuleConstraint._inventory[self.name] = self


class Rule(CommonMixin, JsonMixin, MessageMixin, FollowerMixin, StatusMixing, Base):
    SEVERITY_SOFT = 0
    SEVERITY_ENFORCED = 1

    TYPE_SQL = 0
    TYPE_UNIQUE = 1
    TYPE_CHECK = 2

    name = Column(String, nullable=False, unique=True)
    model_name = Column(String, nullable=False)
    statement = Column(String, nullable=False)
    description = Column(String, nullable=False)
    builtin = Column(Boolean, nullable=False, default=False)
    severity = Column(SmallInteger, nullable=False, default=SEVERITY_SOFT, server_default=str(SEVERITY_SOFT))
    type = Column(SmallInteger, nullable=False, default=TYPE_SQL, server_default=str(TYPE_SQL))
    field = Column(String, nullable=True)

    @hybrid_property
    def summary(self):
        return self.name

    @classmethod
    def verify(cls, obj=None, errors=None, severity=None):
        """
        Run linter rule.
        When `obj` is defined, return rule related to this specific model

        Handling error

        When `errors` is set to "raise", will raise an exception on first error.

        When `severity` is defined filter rule base of the given severity.
        """
        assert obj is None or (hasattr(obj.__class__, '__tablename__') and obj.id), 'obj must be None or a model'
        assert errors is None or errors == 'raise'
        assert severity in [None, Rule.SEVERITY_SOFT, Rule.SEVERITY_ENFORCED]

        # Query list of rules matching our object type and severity to limit the scope of analysis.
        query_rules = Rule.query.filter(Rule.status == Rule.STATUS_ENABLED, Rule.type == Rule.TYPE_SQL)
        if severity:
            query_rules = query_rules.filter(Rule.severity == severity)
        if obj:
            model_name = obj.__class__.__tablename__
            query_rules = query_rules.filter(Rule.model_name == model_name)

        # Combine matching rules with UNION ALL to return list of errors.
        matching_rules = query_rules.all()
        sql = ' UNION ALL '.join(rule._wrap_statement(obj) for rule in matching_rules)
        # If the SQL is empty, we don't have anything to execute.
        if not sql:
            return []

        # On error do something for each row.
        if errors == 'raise':
            row = Rule.session.execute(text(sql)).first()
            if row:
                raise RuleError(row)
        return Rule.session.execute(text(sql)).all()

    def _wrap_statement(self, obj=None, new_statement=None):
        name = self.name.replace("'", "''")
        description = (self.description or '').replace("'", "''")
        field = (self.field or '').replace("'", "''")
        severity = int(self.severity or Rule.SEVERITY_SOFT)
        model_name = self.model_name
        statement = new_statement or self.statement
        # Support 2 columns (id, summary)
        sql = f"SELECT '{name}' as rule_name, '{description}' as description, id, '{model_name}' as model_name, name, '{field}' as field, {severity} as severity FROM ({statement}) as r{self.id}"
        # Add filter if an object is specified.
        if obj:
            sql += f" WHERE id = {obj.id}"
        return sql

    def _validate(self):
        """
        Used to validate the SQL statement before saving it into database to make sure it's a "valid" SQL.
        """
        # Do not validate other type than SQL.
        if not (self.type is None or self.type == Rule.TYPE_SQL):
            # Skip validation
            return

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
            ]
            if fields != expected_fields:
                raise ValueError(
                    'statement',
                    _(
                        "your statement returned %s column(s) label as %s, but it's expected to return 2 columns labeled as: %s"
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
    """
    Validate SQL Statement
    """
    instance._validate()


@event.listens_for(Rule, "before_insert")
def before_insert(mapper, connection, instance):
    """
    Validate SQL Statement
    """
    instance._validate()


@event.listens_for(Base.metadata, 'after_create')
def create_update_rule(target, conn, **kw):
    """
    Update builtin rule on application start.
    """
    # Create new column "field"
    if not column_exists(conn, Rule.field):
        column_add(conn, Rule.field)
    # Create new column "type"
    if not column_exists(conn, Rule.type):
        column_add(conn, Rule.type)

    # To allow usage of ORM session within DDL scope, we need to manually assign the connection to our current session.
    Rule.session.bind = conn

    # Rule to be deleted
    Rule.query.filter(Rule.name.in_(['dhcprecord_ip_invalid_subnet'])).delete()

    # For each soft rule register, make sure to create it in database
    for rule in RuleConstraint._inventory.values():
        obj = Rule.query.filter(Rule.name == rule.name).first()
        if not obj:
            obj = Rule(name=rule.name)
        try:
            # Generate SQL
            statement = rule.statement
            if hasattr(statement, '__call__'):
                statement = statement()
            sql = str(statement.compile(conn.engine, compile_kwargs={"literal_binds": True}))
            # Update database
            obj.description = str(rule.info.get('description', ''))
            obj.severity = rule.severity
            obj.field = str(rule.info.get('field', None))
            obj.model_name = rule.model_name
            obj.statement = sql
            obj.builtin = True
            obj.type = Rule.TYPE_SQL
            obj.add().flush()
        except Exception:
            logger.exception('fail to add rule in database')

    # For each CheckConstraint, create rule to be displayed in UI.
    for constraint in _list_constraints():
        obj = Rule.query.filter(Rule.name == constraint.name).first()
        if not obj:
            obj = Rule(name=constraint.name)
        try:
            # Update database
            obj.description = str(constraint.info.get('description', ''))
            obj.severity = Rule.SEVERITY_ENFORCED
            obj.field = str(constraint.info.get('field', None))
            obj.model_name = constraint.table.name
            obj.statement = "CHECK CONSTRAINT %s" % constraint.sqltext
            obj.builtin = True
            obj.type = Rule.TYPE_CHECK
            obj.add().flush()
        except Exception:
            logger.exception('fail to load constraint in database')

    # For each unique index, create rule to be displayed in UI.
    for index in _list_indexes():
        obj = Rule.query.filter(Rule.name == index.name).first()
        if not obj:
            obj = Rule(name=index.name)
        try:
            # Update database
            obj.description = str(index.info.get('description', ''))
            obj.severity = Rule.SEVERITY_ENFORCED
            obj.field = str(index.info.get('field', None))
            obj.model_name = index.table.name
            obj.statement = str(ddl.CreateIndex(index))
            obj.builtin = True
            obj.type = Rule.TYPE_UNIQUE
            obj.add().flush()
        except Exception:
            logger.exception('fail to load unique index in database')
