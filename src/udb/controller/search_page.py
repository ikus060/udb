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
from sqlalchemy import or_
from wtforms.fields import StringField
from wtforms.validators import InputRequired, Length

from udb.controller import url_for
from udb.controller.form import CherryForm
from udb.core.model import Message, Search

Base = cherrypy.tools.db.get_base()


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
    def index(self, **kwargs):
        form = SearchForm()
        return {
            'form': form,
        }

    @cherrypy.expose()
    @cherrypy.tools.json_out()
    def query_json(self, **kwargs):
        form = SearchForm()
        if not form.validate():
            return {'data': []}
        query = Search.query.filter(
            or_(
                Search._search_vector.websearch(form.q.data),
                Search.messages.any(Message._search_vector.websearch(form.q.data)),
            )
        )
        query = query.order_by(Search.modified_at)
        return {
            'data': [
                {
                    'url': url_for(obj, 'edit'),
                    'summary': obj.summary,
                    'owner_id': obj.owner_id,
                    'owner': obj.owner.to_json() if obj.owner else None,
                    'notes': obj.notes,
                }
                for obj in query.all()
            ]
        }
