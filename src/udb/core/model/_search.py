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
from sqlalchemy import and_, literal, select, union
from sqlalchemy.orm import foreign, relationship, remote

from udb.core.model import DhcpRecord, DnsRecord, DnsZone, Message, Subnet, User, Vrf

Base = cherrypy.tools.db.get_base()


search_query = union(
    *[
        select(
            literal(model.__name__.lower()).label('model_name'),
            model.id.label('model_id'),
            model.summary,
            model.notes,
            model.status,
            model.owner_id,
            model.modified_at,
            model._search_vector,
        )
        for model in [DhcpRecord, DnsRecord, DnsZone, Subnet, Vrf]
    ]
).subquery()


class Search(Base):
    __table__ = search_query
    __mapper_args__ = {'primary_key': [search_query.c.model_id, search_query.c.model_name]}
    owner = relationship(User, lazy=False)
    messages = relationship(
        Message,
        primaryjoin=lambda: and_(
            Search.model_name == remote(foreign(Message.model_name)),
            Search.model_id == remote(foreign(Message.model_id)),
        ),
        viewonly=True,
    )
