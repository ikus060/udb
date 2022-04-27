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
from sqlalchemy import and_

from udb.core.model import Follower, Search


class NotificationsPage:
    @cherrypy.expose()
    @cherrypy.tools.jinja2(template=['notifications.html'])
    def index(self, **kwargs):
        userobj = cherrypy.request.currentuser
        query = Search.query.join(
            Follower, and_(Search.model_name == Follower.model_name, Search.id == Follower.model_id)
        ).filter(Follower.user_id == userobj.id)
        obj_list = query.all()
        return {'obj_list': obj_list}
