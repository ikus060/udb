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
from sqlalchemy import event

from ._dhcprecord import DhcpRecord  # noqa
from ._dnsrecord import DnsRecord  # noqa
from ._dnszone import DnsZone  # noqa
from ._follower import Follower  # noqa
from ._ip import Ip  # noqa
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

    def exists(column):
        table_name = column.table.fullname
        column_name = column.name
        if 'SQLite' in connection.engine.dialect.__class__.__name__:
            sql = "SELECT COUNT(*) FROM pragma_table_info('%s') WHERE LOWER(name)=LOWER('%s')" % (
                table_name,
                column_name,
            )
        else:
            sql = "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='%s' and column_name='%s'" % (
                table_name,
                column_name,
            )
        data = connection.engine.execute(sql).first()
        return data[0] >= 1

    def add_column(column):
        if exists(column):
            return
        table_name = column.table.fullname
        column_name = column.name
        column_type = column.type.compile(connection.engine.dialect)
        connection.engine.execute('ALTER TABLE %s ADD COLUMN %s %s' % (table_name, column_name, column_type))

    if getattr(connection, '_transaction', None):
        connection._transaction.commit()

    # Add Message.sent
    add_column(Message.__table__.c.sent)
