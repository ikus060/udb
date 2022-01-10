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
from markupsafe import Markup, escape
from sqlalchemy import Column, String, Table, event, inspect
from sqlalchemy.orm import (declarative_mixin, declared_attr, relationship,
                            validates)
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.schema import ForeignKey
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
        if attr.key in ignore_fields:
            continue

        hist = state.get_history(attr.key, True)

        if not hist.has_changes():
            continue

        old_value = hist.deleted[0] if hist.deleted else None
        new_value = hist.added[0] if hist.added else None
        changes[attr.key] = [old_value, new_value]

    return changes


@event.listens_for(Session, "before_flush")
def before_flush(session, flush_context, instances):
    for obj in session.dirty:
        if hasattr(obj, 'messages'):
            changes = _get_model_changes(
                obj, ignore_fields=['messages', 'followers'])
            if not changes:
                continue
            # TODO How to get the real author_id ?
            try:
                body = json.dumps(changes)
            except Exception:
                body = str(changes)
            message = Message(author_id=1, body=body)
            session.add(message)
            obj.messages.append(message)


class Message(Base):
    __tablename__ = 'message'
    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    author = relationship("User")
    subject = Column(String, nullable=False, default='')
    # When body start with a "{" the content is a json changes.
    body = Column(String, nullable=False)
    date = Column(DateTime, default=func.now())
    # TODO message_type: email, comments

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

    def __html__(self):
        """
        HTML Representation of this  messages. Either the body as HTML or JSON changes as HTML.
        """
        changes = self.changes

        def generator():
            if changes:
                yield Markup('<ul>')
                for key, values in changes.items():
                    old_value, new_value = values
                    yield Markup('<li><b>%s</b>: %s → %s</li>' % (escape(key), escape(old_value), escape(new_value)))
                yield Markup('</ul>')
            else:
                yield Markup('<p>')
                yield Markup.escape(self.body)
                yield Markup('</p>')

        return Markup('').join(list(generator()))


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

    @declared_attr
    def messages(cls):
        messages_association = Table(
            "%s_messages" % cls.__tablename__,
            cls.metadata,
            Column("message_id", ForeignKey("message.id"),
                   primary_key=True),
            Column("%s_id" % cls.__tablename__,
                   ForeignKey("%s.id" % cls.__tablename__),
                   primary_key=True),
        )
        return relationship(
            Message,
            secondary=messages_association,
            backref="%s_parents" % cls.__name__.lower(),
            lazy='select')

    @declared_attr
    def followers(cls):
        followers_association = Table(
            "%s_followers" % cls.__tablename__,
            cls.metadata,
            Column("user_id", ForeignKey("user.id"),
                   primary_key=True),
            Column("%s_id" % cls.__tablename__,
                   ForeignKey("%s.id" % cls.__tablename__),
                   primary_key=True),
        )
        return relationship(
            User,
            secondary=followers_association,
            backref="%s_parents" % cls.__name__.lower(),
            lazy='select')

    id = Column(Integer, primary_key=True)
    notes = Column(String, nullable=False, default='')
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    modified_at = Column(DateTime, nullable=False,
                         server_default=func.now(), onupdate=func.now())
    status = Column(String, default=STATUS_ENABLED)

    def is_following(self, user):
        """
        Check if the given user is following this object.
        """
        return user in self.followers

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
