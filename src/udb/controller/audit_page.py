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


from collections import namedtuple

import cherrypy
from sqlalchemy import and_, desc, func, literal, select, union_all

from udb.controller import url_for, validate_int
from udb.core.model import Message, User, auditable_models
from udb.tools.i18n import gettext as _

AuditRow = namedtuple(
    'AuditRow', ['model_id', 'status', 'summary', 'model_name', 'author', 'date', 'type', 'body', 'changes', 'url']
)

AllModel = union_all(
    *[
        select(
            literal(model.__tablename__.lower()).label('model_name'),
            model.id.label('model_id'),
            getattr(model, 'status', literal('enabled')).label('status'),
            model.summary,
            getattr(model, 'search_string', model.summary).label('search_string'),
        )
        for model in auditable_models
    ]
).alias()


class AuditPage:
    @cherrypy.expose()
    @cherrypy.tools.jinja2(template=['audit/list.html'])
    def index(self):
        return {'model_names': [model.__tablename__ for model in auditable_models]}

    @cherrypy.expose()
    @cherrypy.tools.json_out()
    def data_json(self, draw=None, start='0', length='10', **kwargs):
        """
        Return list of messages.
        """
        start = validate_int(start, min=0)
        length = validate_int(length, min=1, max=100)

        # Run the queries
        query = (
            Message.query.with_entities(
                Message.model_id,
                AllModel.c.status,
                AllModel.c.summary,
                Message.model_name,
                User.summary.label('author'),
                Message.date,
                Message.type,
                Message.body,
                Message._changes.label('changes'),
            )
            .outerjoin(Message.author)
            .outerjoin(
                AllModel,
                and_(
                    Message.model_name == AllModel.c.model_name,
                    Message.model_id == AllModel.c.model_id,
                ),
            )
            .filter(Message.type.in_([Message.TYPE_NEW, Message.TYPE_DIRTY]))
        )

        # Get total count before filtering
        total = query.count()

        # Apply sorting - default sort by date
        order_idx = validate_int(
            kwargs.get('order[0][column]', '5'),
            min=0,
            max=len(query.column_descriptions) - 1,
            message=_('Invalid column for sorting'),
        )
        order_dir = kwargs.get('order[0][dir]', 'desc')
        order_col = query.column_descriptions[int(order_idx)]['expr']
        if order_dir == 'desc':
            query = query.order_by(desc(order_col))
        else:
            query = query.order_by(order_col)

        # Apply filtering
        search = kwargs.get('search[value]', '')
        if search:
            query = query.filter(func.udb_websearch(AllModel.c.search_string, search))

        # Apply model_name filtering
        model_name = kwargs.get('columns[3][search][value]', '')
        if model_name:
            query = query.filter(AllModel.c.model_name == model_name)

        # Count result.
        filtered = query.count()
        data = query.offset(start).limit(length).all()

        # Return data as Json
        return {
            'draw': draw,
            'recordsTotal': total,
            'recordsFiltered': filtered,
            'data': [
                AuditRow(
                    model_id=obj.model_id,
                    status=obj.status,
                    summary=obj.summary,
                    model_name=obj.model_name,
                    author=obj.author,
                    date=obj.date.isoformat(),
                    type=obj.type,
                    body=obj.body,
                    changes=Message.json_changes(obj.changes),
                    url=url_for(obj.model_name, obj.model_id, 'edit', relative='server'),
                )
                for obj in data
            ],
        }
