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
from sqlalchemy import literal, select, union
from wtforms.fields import StringField
from wtforms.validators import InputRequired, Length

from udb.controller import url_for
from udb.controller.form import CherryForm
from udb.core.model import DhcpRecord, DnsRecord, DnsZone, Subnet, Vrf

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

    def _list_query(self, value):
        session = cherrypy.tools.db.get_session()
        return session.query(
            union(
                *[
                    select(
                        literal(model.__name__.lower()).label('model_name'),
                        model.id.label('model_id'),
                        model.summary,
                        model.notes.label('notes'),
                        model.modified_at.label('modified_at'),
                        model._search_vector,
                    ).filter(
                        model._search_vector.websearch(value),
                    )
                    for model in [DhcpRecord, DnsRecord, DnsZone, Subnet, Vrf]
                ]
            ).subquery()
        ).limit(100)

    @cherrypy.expose()
    @cherrypy.tools.json_out()
    def query_json(self, **kwargs):
        form = SearchForm()
        if not form.validate():
            return {'data': []}
        query = self._list_query(form.q.data)
        return {
            'data': [
                {
                    'url': url_for(obj, 'edit', relative='server'),
                    'summary': obj.summary,
                    'notes': obj.notes,
                    'model_name': obj.model_name,
                }
                for obj in query
            ]
        }
