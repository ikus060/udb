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

import itertools
import json

import cherrypy
from sqlalchemy import Boolean, Column, String, and_, event, inspect
from sqlalchemy.orm import backref, declared_attr, foreign, relationship, remote
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.sql.sqltypes import Integer

import udb.tools.db  # noqa: import cherrypy.tools.db
from udb.tools.i18n import gettext as _

from ._json import JsonMixin
from ._search_string import SearchableMixing
from ._timestamp import Timestamp

Base = cherrypy.tools.db.get_base()
Session = cherrypy.tools.db.get_session()


def _get_model_changes(model, ignore=['messages']):
    """
    Return a dictionary containing changes made to the model since it was
    fetched from the database.

    The dictionary is of the form {'property_name': [old_value, new_value]}
    """
    state = inspect(model)
    changes = {}
    for attr in state.attrs:
        hist = attr.load_history()
        if not hist.has_changes():
            continue
        # Ignore `messages` field and other private field
        if attr.key == 'messages' or attr.key.startswith('_'):
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
    change_type = 'dirty' if state.has_identity else 'new'
    return change_type, changes


@event.listens_for(Session, "before_flush")
def create_messages(session, flush_context, instances):
    """
    When object get updated, add an audit message.
    """
    # Get current user
    author_id = None
    currentuser = getattr(cherrypy.serving.request, 'currentuser', None)
    if currentuser:
        author_id = currentuser.id
    # Create message if object is created or modified
    for obj in itertools.chain(session.new, session.dirty):
        if hasattr(obj, 'add_message'):
            # compute the list of changes base on sqlalchemy history
            change_type, changes = _get_model_changes(obj)
            if not changes:
                continue

            # Store changes as Json string
            try:
                changes = json.dumps(changes, default=str)
            except Exception:
                changes = str(changes)

            # Append the changes to a new message or a message in the current session flush.
            message = next((msg for msg in session.new if isinstance(msg, Message) and msg.model_object == obj), False)
            if not message:
                message = Message(author_id=author_id, _changes=changes, type=change_type)
                obj.add_message(message)
            else:
                message._changes = changes
                message.type = change_type
                message.add()


class Message(JsonMixin, SearchableMixing, Base):
    TYPE_COMMENT = 'comment'
    TYPE_NEW = 'new'
    TYPE_DIRTY = 'dirty'

    __tablename__ = 'message'
    id = Column(Integer, primary_key=True)
    model_name = Column(String, nullable=False)
    model_id = Column(Integer, nullable=False)
    author_id = Column(Integer, ForeignKey('user.id'), nullable=True)
    author = relationship("User", lazy=False)
    type = Column(String, nullable=False, default=TYPE_COMMENT)
    body = Column(String, nullable=False, default='')
    _changes = Column('changes', String, nullable=True)
    date = Column(Timestamp(timezone=True), default=func.now())
    sent = Column(Boolean, default=False)

    @property
    def changes(self):
        """
        Return Json changes stored in message.
        """
        return Message.json_changes(self._changes)

    @classmethod
    def _search_string(cls):
        return cls.body + " " + cls._changes

    @property
    def model_object(self):
        """
        Return the model instance related to this message. All object supporting messages create a backref with <tablename>_model.
        """
        if self.model_name is None:
            return None
        return getattr(self, "%s_object" % self.model_name)

    def get_summary(self):
        """
        Provide a summary to be displayed in table.
        """
        model_object = getattr(self, "%s_object" % self.model_name, None)
        if model_object:
            return model_object.summary

    @property
    def author_name(self):
        if self.author is None:
            return _('nobody')
        return str(self.author)

    @classmethod
    def json_changes(cls, value):
        """
        Safely convert a string to Json data.
        """
        if not value or value[0] != '{':
            return None
        try:
            return json.loads(value)
        except Exception:
            return None


class MessageMixin:
    """
    Mixin to support messages.
    """

    def add_message(self, message):
        message.model_name = self.__tablename__
        self.messages.append(message)

    @declared_attr
    def messages(cls):
        return relationship(
            Message,
            primaryjoin=lambda: and_(
                cls.__tablename__ == remote(foreign(Message.model_name)), cls.id == remote(foreign(Message.model_id))
            ),
            order_by=Message.date,
            lazy=True,
            cascade="all, delete",
            overlaps="messages,dnsrecord_object,dnszone_object,subnet_object,dhcprecord_object,ip_object,mac_object,environment_object,vrf_object,user_object,softrule_object",
            backref=backref(
                '%s_object' % cls.__tablename__,
                lazy=True,
                overlaps="messages,dnsrecord_object,dnszone_object,subnet_object,dhcprecord_object,ip_object,mac_object,environment_object,vrf_object,user_object,softrule_object",
            ),
        )

    @declared_attr
    def comments(cls):
        return relationship(
            Message,
            primaryjoin=lambda: and_(
                cls.__tablename__ == remote(foreign(Message.model_name)),
                cls.id == remote(foreign(Message.model_id)),
                Message.type == Message.TYPE_COMMENT,
            ),
            order_by=Message.date,
            viewonly=True,
            lazy=True,
        )

    @declared_attr
    def changes(cls):
        return relationship(
            Message,
            primaryjoin=lambda: and_(
                cls.__tablename__ == remote(foreign(Message.model_name)),
                cls.id == remote(foreign(Message.model_id)),
                Message.type.in_([Message.TYPE_NEW, Message.TYPE_DIRTY]),
            ),
            order_by=Message.date,
            viewonly=True,
            lazy=True,
        )

    def objects_to_notify(self):
        """
        Return a list of tuple with model_name and id to get notified whenever this object is modified.

        Object could return it self or it's parent.
        """
        return [(self.__tablename__, self.id)]
