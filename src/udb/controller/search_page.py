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
from wtforms.validators import input_required

from udb.controller import flash
from udb.controller.form import CherryForm
from udb.core.model import Message, Search

Base = cherrypy.tools.db.get_base()


class SearchForm(CherryForm):
    q = StringField(validators=[input_required()])

    def is_submitted(self):
        return cherrypy.request.method in ['GET']


class SearchPage:
    @cherrypy.expose()
    @cherrypy.tools.jinja2(template=['search.html'])
    def index(self, **kwargs):
        form = SearchForm()
        if not form.validate():
            flash('TODO ERROR MESSAGE')
            obj_list = []
        else:
            obj_list = self._query(form.q.data)
        return {
            'form': form,
            'obj_list': obj_list,
        }

    def _query(self, term):
        """
        Build a query with supported feature of the current object class.
        """
        query = Search.query.filter(
            or_(Search._search_vector.websearch(term), Search.messages.any(Message._search_vector.websearch(term)))
        )
        query = query.order_by(Search.modified_at)
        # TODO Limit record (50 by default)
        # TODO Filter record types
        return query.all()
