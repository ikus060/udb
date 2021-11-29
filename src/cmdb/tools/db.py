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
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base


class BaseExtensions(DeclarativeMeta):
    '''
    Extends declarative base to provide convenience methods to models similar to
    functionality found in Elixir. Works in python3.

    For example, given the model User:
    # no need to write init methods for models, simply pass keyword arguments or
    # override if needed.
    User(name="daniel", email="daniel@dasa.cc") # is automatically added to session
    User.query # returns session.query(User)
    User.query.all() # instead of session.query(User).all()
    changed = User.from_dict({}) # update record based on dict argument passed in and returns any keys changed
    '''

    def __init__(self, name, bases, class_dict):
        DeclarativeMeta.__init__(self, name, bases, class_dict)

    @property
    def query(self):
        return self.session.query(self)

    @property
    def session(self):
        # get contents of string 'Engine(...)'
        dburi = repr(self.__base__.metadata.bind)[7:-1]
        return cherrypy.tools.db.get_session(dburi)


class SQLA(cherrypy.Tool):
    _name = 'sqla'
    _bases = {}
    _sessions = {}

    def __init__(self, **kw):
        cherrypy.Tool.__init__(self, None, None, priority=20)

    def _setup(self):
        conf = self._merged_args()
        cherrypy.request.hooks.attach(
            'on_start_resource', self.on_start_resource, **conf)
        cherrypy.request.hooks.attach('on_end_resource', self.on_end_resource)

    def create_all(self):
        for v in self._bases.values():
            v.metadata.create_all()

    def get_base(self, dburi='sqlite:///www.sqlite'):
        base = self._bases.get(dburi)
        if base is None:
            self._bases[dburi] = base = declarative_base(
                metaclass=BaseExtensions)
            base.metadata.bind = create_engine(dburi, echo=True)

        if self._sessions.get(dburi) is None:
            self._sessions[dburi] = session = scoped_session(
                sessionmaker(autoflush=True, autocommit=False))
            session.configure(bind=base.metadata.bind)

        return base

    def get_session(self, dburi='sqlite:///www.sqlite'):
        return self._sessions.get(dburi)

    def on_start_resource(self, echo=None):
        if echo is not None:
            for session in self._sessions.values():
                session.bind.echo = echo

    def on_end_resource(self):
        for session in self._sessions.values():
            try:
                session.flush()
                session.commit()
            except:
                session.rollback()
                session.expunge_all()
            finally:
                session.remove()


cherrypy.tools.db = SQLA()
