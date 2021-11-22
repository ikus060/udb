# -*- coding: utf-8 -*-
# cmdb, A web interface to manage IT network CMDB
# Copyright (C) 2021 IKUS Software inc.
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
'''
SQLAlchemy Tool for CherryPy.
'''
import cherrypy
from cherrypy.process import plugins
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker


class SQLAlchemyPlugin(plugins.SimplePlugin):
    def __init__(self, bus, orm_base, dburi, **kw):
        plugins.SimplePlugin.__init__(self, bus)
        self.dburi = dburi
        self.orm_base = orm_base
        self.create_kwargs = kw

        self.bus.subscribe('db.bind', self.bind)
        self.bus.subscribe('db.create', self.create)
        self.bus.subscribe('db.drop', self.drop)

        self.sa_engine = None

    def start(self):
        self.sa_engine = create_engine(self.dburi, **self.create_kwargs)

    def create(self):
        if not self.sa_engine:
            self.start()
        cherrypy.log('Creating tables: %s' % self.sa_engine)
        self.orm_base.metadata.bind = self.sa_engine
        self.orm_base.metadata.create_all(self.sa_engine)

    def drop(self):
        if not self.sa_engine:
            self.start()
        cherrypy.log('Drop tables: %s' % self.sa_engine)
        self.orm_base.metadata.bind = self.sa_engine
        self.orm_base.metadata.drop_all(self.sa_engine)

    def stop(self):
        if self.sa_engine:
            self.sa_engine.dispose()
            self.sa_engine = None

    def bind(self, session):
        session.configure(bind=self.sa_engine)


class SQLAlchemyTool(cherrypy.Tool):
    def __init__(self, **kw):
        cherrypy.Tool.__init__(self, 'on_start_resource',
                               self.bind_session,
                               priority=20)

        self.session = scoped_session(sessionmaker(**kw))

    def _setup(self):
        cherrypy.Tool._setup(self)
        cherrypy.request.hooks.attach('on_end_resource',
                                      self.commit_transaction,
                                      priority=80)

    def bind_session(self):
        cherrypy.engine.publish('db.bind', self.session)
        cherrypy.request.session = self.session

    def commit_transaction(self):
        cherrypy.request.session = None
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        finally:
            self.session.remove()
        self.session.close()


cherrypy.tools.db = SQLAlchemyTool()
