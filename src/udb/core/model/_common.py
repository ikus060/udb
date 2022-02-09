# -*- coding: utf-8 -*-
# udb, A web interface to manage IT network
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

import json

import cherrypy
import udb.tools.db  # noqa: import cherrypy.tools.db
from sqlalchemy import Column, String, event, inspect
from sqlalchemy.orm import (declarative_mixin, declared_attr, relationship,
                            validates)
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.schema import ForeignKey, Index
from sqlalchemy.sql.sqltypes import DateTime, Integer

from ._user import User

Base = cherrypy.tools.db.get_base()
Session = cherrypy.tools.db.get_session()


def _get_model_changes(model, ignore_fields=[]):
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
                hist.added[0] if len(hist.added) >= 1 else None]
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


class Message(Base):
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


class Follower(Base):
    __tablename__ = 'follower'

    id = Column(Integer, primary_key=True)
    model = Column(String, nullable=False)
    model_id = Column(Integer, nullable=False)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    user = relationship(User)


# Create a unique index for username
Index('follower_index', Follower.model,
      Follower.model_id, Follower.user_id, unique=True)


@declarative_mixin
class CommonMixin(object):
    """
    Mixin for common item properties.
    """
    STATUS_ENABLED = 'enabled'
    STATUS_DISABLED = 'disabled'
    STATUS_DELETED = 'deleted'

    STATUS = [STATUS_ENABLED, STATUS_DISABLED, STATUS_DELETED]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    @declared_attr
    def owner_id(cls):
        return Column(Integer, ForeignKey('user.id'))

    @declared_attr
    def owner(cls):
        return relationship("User")

    id = Column(Integer, primary_key=True)
    notes = Column(String, nullable=False, default='')
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    modified_at = Column(DateTime, nullable=False,
                         server_default=func.now(), onupdate=func.now())
    status = Column(String, default=STATUS_ENABLED)

    def add_follower(self, user, commit=True):
        assert self.id
        assert user
        if not self.is_following(user):
            f = Follower(
                model=self.__tablename__,
                model_id=self.id,
                user=user)
            f.add(commit=commit)

    def remove_follower(self, user):
        assert self.id
        assert user
        assert user.id
        f = Follower.query.where(
            Follower.model == self.__tablename__,
            Follower.model_id == self.id,
            Follower.user == user).first()
        if f:
            f.delete()

    def get_followers(self):
        """
        Return list of followers for this object.
        """
        return User.query.join(Follower).where(Follower.model == self.__tablename__, Follower.model_id == self.id).all()

    def is_following(self, user):
        """
        Check if the given user is following this object.
        """
        return Follower.query.where(
            Follower.model == self.__tablename__,
            Follower.model_id == self.id,
            Follower.user == user).first() is not None

    def get_messages(self, type=None):
        """
        Return list of messages related to this object for the given type.
        """
        query = Message.query.where(
            Message.model == self.__tablename__,
            Message.model_id == self.id)
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

    @validates('status')
    def validate_status(self, key, value):
        if value not in CommonMixin.STATUS:
            raise ValueError(value)
        return value

    def to_json(self):
        def _value(value):
            if hasattr(value, 'isoformat'):  # datetime
                return value.isoformat()
            return value
        return {
            c.name: _value(getattr(self, c.name))
            for c in self.__table__.columns
        }

    def from_json(self, data):
        for k, v in data.items():
            setattr(self, k, v)