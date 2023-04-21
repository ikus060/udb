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
from sqlalchemy import event, text
from sqlalchemy.sql import ddl
from sqlalchemy.sql.schema import Index

from . import _group_concat  # noqa
from ._deployment import Deployment, Environment  # noqa
from ._dhcprecord import DhcpRecord  # noqa
from ._dnsrecord import DnsRecord  # noqa
from ._dnszone import DnsZone  # noqa
from ._follower import Follower  # noqa
from ._ip import Ip  # noqa
from ._mac import Mac  # noqa
from ._message import Message  # noqa
from ._subnet import Subnet, SubnetRange  # noqa
from ._user import User  # noqa
from ._vrf import Vrf  # noqa

from ._search import Search  # noqa # isort: skip

Base = cherrypy.tools.db.get_base()


@event.listens_for(Base.metadata, 'after_create')
def db_after_create(target, connection, **kw):
    """
    Called on database creation to update database schema.
    """

    # SQLAlchmey 1.4 Commit current transaction and open a new one.
    if getattr(connection, '_transaction', None):
        connection._transaction.commit()

    with connection.engine.connect() as connection:

        def exists(column):
            table_name = column.table.fullname
            column_name = column.name
            if 'SQLite' in connection.engine.dialect.__class__.__name__:
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

        # Add Message.sent
        add_column(Message.__table__.c.sent)

        # Add Message.changes - if created, move data from body to changes.
        if add_column(Message.__table__.c.changes):
            Message.query.filter(Message.body.startswith('{')).update(
                {Message.body: '', Message._changes: Message.body}, synchronize_session=False
            )

        # Add 'token' to deployment
        add_column(Deployment.__table__.c.token)
        # Add 'status' to environment
        add_column(Environment.__table__.c.status)
        # Add 'lang' to user
        add_column(User.__table__.c.lang)
        # Add rir_status column
        add_column(Subnet.__table__.c.rir_status)
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

        # SQLAlchmey 1.4 Commit current transaction and open a new one.
        if getattr(connection, '_transaction', None):
            connection._transaction.commit()
