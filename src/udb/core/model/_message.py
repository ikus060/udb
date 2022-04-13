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

import json

import cherrypy
from sqlalchemy import Column, String, event, inspect
from sqlalchemy.orm import relationship
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.sql.sqltypes import DateTime, Integer

import udb.tools.db  # noqa: import cherrypy.tools.db

from ._search_vector import SearchableMixing

Base = cherrypy.tools.db.get_base()
Session = cherrypy.tools.db.get_session()


def _get_model_changes(model):
    """
    Return a dictionary containing changes made to the model since it was
    fetched from the database.

    The dictionary is of the form {'property_name': [old_value, new_value]}

    Example:
        user = get_user_by_id(420)
        >>> '<User id=402 email="business_email@gmail.com">'
        get_model_changes(user)
        >>> {}
        user.email = 'new_email@who-dis.biz'
        get_model_changes(user)
        >>> {'email': ['business_email@gmail.com', 'new_email@who-dis.biz']}
    """
    state = inspect(model)
    changes = {}
    for attr in state.attrs:
        hist = attr.load_history()
        if not hist.has_changes():
            continue
        if isinstance(attr.value, (list, tuple)) or len(hist.deleted) > 1 or len(hist.added) > 1:
            # If array, store array
            changes[attr.key] = [hist.deleted, hist.added]
        else:
            # If primitive, store primitive
            changes[attr.key] = [
                hist.deleted[0] if len(hist.deleted) >= 1 else None,
                hist.added[0] if len(hist.added) >= 1 else None,
            ]
    return changes


@event.listens_for(Session, "before_flush")
def before_flush(session, flush_context, instances):
    """
    When object get updated, add an audit message.
    """
    # Get current user
    author_id = None
    currentuser = getattr(cherrypy.serving.request, 'currentuser', None)
    if currentuser:
        author_id = currentuser.id
    # Create message if object changed.
    for obj in session.dirty:
        if hasattr(obj, 'add_message'):
            changes = _get_model_changes(obj)
            if not changes:
                continue
            try:
                body = json.dumps(changes, default=str)
            except Exception:
                body = str(changes)
            message = Message(author_id=author_id, body=body, type='dirty')
            obj.add_message(message, commit=False)


@event.listens_for(Session, "after_flush")
def after_flush(session, flush_context):
    """
    When object get created, add an audit message.
    """
    # Get current user
    author_id = None
    currentuser = getattr(cherrypy.serving.request, 'currentuser', None)
    if currentuser:
        author_id = currentuser.id
    # Create message if object is created.
    for obj in session.new:
        if hasattr(obj, 'add_message'):
            changes = _get_model_changes(obj)
            try:
                body = json.dumps(changes, default=str)
            except Exception:
                body = str(changes)
            message = Message(author_id=author_id, body=body, type='new')
            obj.add_message(message, commit=False)


class Message(SearchableMixing, Base):
    __tablename__ = 'message'
    id = Column(Integer, primary_key=True)
    model = Column(String, nullable=False)
    model_id = Column(Integer, nullable=False)
    author_id = Column(Integer, ForeignKey('user.id'), nullable=True)
    author = relationship("User")
    subject = Column(String, nullable=False, default='')
    type = Column(String, nullable=False, default='comment')
    # When body start with a "{" the content is a json changes.
    body = Column(String, nullable=False)
    date = Column(DateTime, default=func.now())

    @property
    def changes(self):
        """
        Return Json changes stored in body.
        """
        if not self.body or not self.body[0] == '{':
            return None
        try:
            return json.loads(self.body)
        except Exception:
            return None

    @classmethod
    def _search_string(cls):
        return cls.body + " " + cls.subject


class MessageMixin:
    """
    Mixin to support messages.
    """

    def get_messages(self, type=None):
        """
        Return list of messages related to this object for the given type.
        """
        query = Message.query.where(Message.model == self.__tablename__, Message.model_id == self.id)
        if type is not None:
            if isinstance(type, (tuple, list)):
                query = query.where(Message.type.in_(type))
            else:
                query = query.where(Message.type == type)
        return query.all()

    def add_message(self, message, commit=True):
        assert self.id
        message.model = self.__tablename__
        message.model_id = self.id
        message.add(commit=commit)
