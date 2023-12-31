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
    'AuditRow', ['model_id', 'status', 'summary', 'model_name', 'author_name', 'date', 'type', 'body', 'changes', 'url']
)

AllModel = union_all(
    *[
        select(
            literal(model.__tablename__.lower()).label('model_name'),
            model.id.label('model_id'),
            getattr(model, 'estatus', literal(User.STATUS_ENABLED)).label('estatus'),
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
                AllModel.c.estatus,
                AllModel.c.summary,
                Message.model_name,
                User.summary.label('author_name'),
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
        # With multiple selection, this is a regex pattern similar to (model1|model2|model3)
        search_model = kwargs.get('columns[3][search][value]', '')
        if search_model:
            model_names = search_model.strip('()').split('|')
            query = query.filter(AllModel.c.model_name.in_(model_names))

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
                    model_id=row.model_id,
                    status=row.estatus,
                    summary=row.summary,
                    model_name=row.model_name,
                    author_name=row.author_name or str(_('System')),
                    date=row.date.isoformat(),
                    type=row.type,
                    body=row.body,
                    changes=Message.json_changes(row.changes),
                    url=url_for(row.model_name, row.model_id, 'edit', relative='server'),
                )
                for row in data
            ],
        }
