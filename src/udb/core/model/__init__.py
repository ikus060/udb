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
import inspect
import time

import cherrypy
from sqlalchemy import event, select, text
from sqlalchemy.sql import ddl
from sqlalchemy.sql.schema import Index

from . import _bool_or  # noqa
from . import _group_concat  # noqa
from ._deployment import Deployment, Environment  # noqa
from ._dhcprecord import DhcpRecord  # noqa
from ._dnsrecord import DnsRecord  # noqa
from ._dnszone import DnsZone  # noqa
from ._follower import Follower  # noqa
from ._ip import Ip  # noqa
from ._mac import Mac  # noqa
from ._message import Message  # noqa
from ._rule import Rule  # noqa
from ._subnet import Subnet, SubnetRange, subnetrange_index, subnetrange_order  # noqa
from ._user import User  # noqa
from ._vrf import Vrf  # noqa

Base = cherrypy.tools.db.get_base()

# Build list of model with 'messages' attributes
all_models = [value for value in locals().values() if inspect.isclass(value) and hasattr(value, '__tablename__')]

# Build list of model with 'followers' attributes
followable_models = [
    value
    for unused, value in locals().items()
    if inspect.isclass(value) and hasattr(value, 'followers') and hasattr(value, '__tablename__')
]
followable_model_name = [value.__tablename__ for value in followable_models]

# Build list of model with 'messages' attributes
auditable_models = [
    value
    for unused, value in locals().items()
    if inspect.isclass(value) and hasattr(value, 'messages') and hasattr(value, '__tablename__')
]

# Build list of searchable model with `search_string` attribute
searchable_models = [
    value
    for unused, value in locals().items()
    if inspect.isclass(value)
    and hasattr(value, 'search_string')
    and hasattr(value, 'summary')
    and hasattr(value, '__tablename__')
]


@event.listens_for(Base.metadata, 'after_create', insert=True)
def update_database_schema(target, connection, **kw):
    """
    Called on database creation to update database schema.
    """

    def _commit():
        # SQLAlchmey 1.4 Commit current transaction and open a new one.
        if getattr(connection, '_transaction', None):
            connection._transaction.commit()

    _commit()

    with connection.engine.connect() as connection:

        def is_sqlite():
            return 'SQLite' in connection.engine.dialect.__class__.__name__

        def exists(column):
            table_name = column.table.fullname
            column_name = column.name
            if is_sqlite():
                sql = 'SELECT %s FROM "%s"' % (column_name, table_name)
                try:
                    connection.execute(text(sql)).first()
                    return True
                except Exception:
                    return False
            else:
                sql = "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='%s' and column_name='%s'" % (
                    table_name,
                    column_name,
                )
                data = connection.execute(text(sql)).first()
                return data[0] >= 1

        def add_column(column):
            if exists(column):
                return False
            table_name = column.table.fullname
            # Compile string representation of the column creation.
            connection.execute(
                text(
                    'ALTER TABLE "%s" ADD COLUMN %s' % (table_name, ddl.CreateColumn(column).compile(connection.engine))
                )
            )
            return True

        def recreate_table(table, query):
            table_name = table.fullname
            temp_table = '%s_temp_%s' % (table_name, int(time.time()))
            # Create new table
            create_table_sql = str(ddl.CreateTable(table).compile(connection.engine)).replace(
                'CREATE TABLE %s' % table_name, 'CREATE TABLE %s' % temp_table
            )
            connection.execute(text(create_table_sql))
            if is_sqlite():
                connection.execute(text("PRAGMA defer_foreign_keys = '1'"))
            # Copy data to new table using the provided query.
            connection.execute(
                text(
                    'INSERT INTO %s (%s) %s'
                    % (temp_table, ','.join([c.name for c in query.columns]), query.compile(connection.engine))
                )
            )
            # Drop previous table
            connection.execute(ddl.DropTable(table))
            # Rename table.
            connection.execute(text('ALTER TABLE %s RENAME TO %s' % (temp_table, table_name)))
            if is_sqlite():
                connection.execute(text("PRAGMA defer_foreign_keys = '0'"))

        # Add Message.sent
        add_column(Message.__table__.c.sent)

        # Add Message.changes - if created, move data from body to changes.
        if add_column(Message.__table__.c.changes):
            _commit()
            Message.query.filter(Message.body.startswith('{')).update(
                {Message.body: '', Message._changes: Message.body}, synchronize_session=False
            )
        # TODO Start this from stractch.
        # TODO Move relevent part to each submodule
        # Create module for add_column, recreate_table, etc.
        # Add 'token' to deployment
        add_column(Deployment.__table__.c.token)
        # Add 'status' to environment
        add_column(Environment.__table__.c.status)
        # Add 'lang' to user
        add_column(User.__table__.c.lang)
        # Add rir_status column
        add_column(Subnet.__table__.c.rir_status)
        # Create column for subnet search and make sure it's populated
        add_column(Subnet.__table__.c._subnet_string)
        # Create search_string
        add_column(Mac.__table__.c.search_string)
        add_column(Ip.__table__.c.search_string)
        add_column(Environment.__table__.c.search_string)
        add_column(DhcpRecord.__table__.c.search_string)
        add_column(DnsRecord.__table__.c.search_string)
        add_column(DnsZone.__table__.c.search_string)
        add_column(Message.__table__.c.search_string)
        add_column(Subnet.__table__.c.search_string)
        add_column(Vrf.__table__.c.search_string)
        # Delete unique index on user's email
        connection.execute(ddl.DropIndex(Index('user_email_key'), if_exists=True))
        # Create DHCP range columns
        if not exists(SubnetRange.__table__.c.dhcp):
            recreate_table(
                SubnetRange.__table__,
                select(SubnetRange.id, SubnetRange.subnet_id, SubnetRange.vrf_id, SubnetRange.range),
            )
            # TODO Might need to re-create sequence.
            # ALTER SEQUENCE...
            connection.execute(ddl.CreateIndex(subnetrange_index, if_not_exists=True))
            connection.execute(ddl.CreateIndex(subnetrange_order, if_not_exists=True))
        # Create status column on rule
        add_column(Rule.__table__.c.status)
        # Add severity column on rule
        add_column(Rule.__table__.c.severity)
        # Do final commit of changes
        _commit()
