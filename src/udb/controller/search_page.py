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
from sqlalchemy import desc, func, literal, select, union_all
from wtforms.fields import StringField
from wtforms.validators import InputRequired, Length

from udb.controller import url_for, validate_int
from udb.controller.form import CherryForm
from udb.core.model import User, searchable_models
from udb.tools.i18n import gettext as _

Base = cherrypy.tools.db.get_base()

SearchableModel = union_all(
    *[
        select(
            literal(model.__tablename__.lower()).label('model_name'),
            model.id.label('model_id'),
            getattr(model, 'status', literal('enabled')).label('status'),
            model.summary,
            model.notes,
            model.owner_id,
            model.modified_at,
            model.search_string,
        )
        for model in searchable_models
    ]
).subquery()

SearchRow = namedtuple(
    'SearchRow', ['model_id', 'status', 'summary', 'model_name', 'owner', 'notes', 'modified_at', 'url']
)


class SearchForm(CherryForm):
    q = StringField(
        validators=[
            InputRequired(),
            Length(max=256),
        ]
    )

    def is_submitted(self):
        return cherrypy.request.method in ['GET']


class SearchPage:
    @cherrypy.expose()
    @cherrypy.tools.jinja2(template=['search.html'])
    def index(self, q=None, **kwargs):
        # Count items per model
        query = (
            select(
                SearchableModel.c.model_name,
                func.count(SearchableModel.c.model_id),
            )
            .filter(
                func.udb_websearch(SearchableModel.c.search_string, q),
            )
            .group_by(SearchableModel.c.model_name)
        )
        session = cherrypy.tools.db.get_session()
        counts = {row[0]: row[1] for row in session.execute(query).all()}
        # Determine active tab
        active = None
        for model_name in counts.keys():
            if model_name in kwargs:
                active = model_name
                break
        form = SearchForm()
        return {
            'active': active,
            'form': form,
            'counts': counts,
        }

    @cherrypy.expose()
    @cherrypy.tools.json_out()
    def data_json(self, q=None, draw=None, start='0', length='10', **kwargs):
        """
        Return list of messages.
        """
        start = validate_int(start, min=0)
        length = validate_int(length, min=1, max=100)

        # Return nothing if query is empty.
        if not q:
            return {'draw': draw, 'recordsTotal': 0, 'recordsFiltered': 0, 'data': []}

        # Build query
        query = select(
            SearchableModel.c.model_id,
            SearchableModel.c.status,
            SearchableModel.c.summary,
            SearchableModel.c.model_name,
            User.summary.label('owner'),
            SearchableModel.c.notes,
            SearchableModel.c.modified_at,
        ).outerjoin(User, User.id == SearchableModel.c.owner_id)

        # Apply query search
        query = query.filter(
            func.udb_websearch(SearchableModel.c.search_string, q),
        )

        # Apply sorting - default sort by date
        order_idx = validate_int(
            kwargs.get('order[0][column]', '2'),
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

        # Apply model_name filtering
        model_name = kwargs.get('columns[3][search][value]')
        if model_name:
            query = query.filter(SearchableModel.c.model_name == model_name)

        # Execute the query
        session = cherrypy.tools.db.get_session()
        filtered = session.execute(select(func.count("*")).select_from(query.subquery())).first()[0]
        data = session.execute(query.offset(start).limit(length)).all()

        # Return data as Json
        return {
            'draw': draw,
            'recordsTotal': filtered,
            'recordsFiltered': filtered,
            'data': [
                SearchRow(
                    model_id=obj.model_id,
                    status=obj.status,
                    summary=obj.summary,
                    model_name=obj.model_name,
                    owner=obj.owner,
                    notes=obj.notes,
                    modified_at=obj.modified_at and obj.modified_at.isoformat(),
                    url=url_for(obj, 'edit', relative='server'),
                )
                for obj in data
            ],
        }

    @cherrypy.expose()
    @cherrypy.tools.json_out()
    def typeahead_json(self, q=None, **kwargs):
        # For typeahead search, only list enabled record.
        query = select(SearchableModel.c.model_id, SearchableModel.c.summary, SearchableModel.c.model_name,).filter(
            SearchableModel.c.status == 'enabled',
            func.udb_websearch(SearchableModel.c.search_string, q),
        )
        session = cherrypy.tools.db.get_session()
        data = [
            {
                'model_id': obj.model_id,
                'model_name': obj.model_name,
                'summary': obj.summary,
                'url': url_for(obj, 'edit', relative='server'),
            }
            for obj in session.execute(query).all()
        ]
        return {
            'status': 200,
            'data': data,
        }
