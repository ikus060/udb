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
from sqlalchemy import desc, func
from wtforms.fields import StringField
from wtforms.validators import InputRequired, Length

from udb.controller import url_for, validate_int
from udb.controller.form import CherryForm
from udb.core.model import Search, User
from udb.tools.i18n import gettext as _

Base = cherrypy.tools.db.get_base()

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
        query = (
            Search.query.with_entities(Search.model_name, func.count(Search.model_id))
            .filter(
                Search.search_vector.websearch(q),
            )
            .group_by(Search.model_name)
        )
        counts = {row[0]: row[1] for row in query.all()}
        form = SearchForm()
        return {
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
        query = Search.query.with_entities(
            Search.model_id,
            Search.status,
            Search.summary,
            Search.model_name,
            User.summary.label('owner'),
            Search.notes,
            Search.modified_at,
        ).outerjoin(User, User.id == Search.owner_id)

        # Apply query search
        query = query.filter(
            Search.search_vector.websearch(q),
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
            query = query.filter(Search.model_name == model_name)

        filtered = query.count()
        data = query.offset(start).limit(length).all()

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
