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


from sqlalchemy import Column, String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declarative_mixin, declared_attr, relationship
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.sql.sqltypes import DateTime, Integer

from ._follower import FollowerMixin
from ._message import MessageMixin
from ._search_vector import SearchableMixing
from ._status import StatusMixing


@declarative_mixin
class CommonMixin(StatusMixing, MessageMixin, FollowerMixin, SearchableMixing):
    """
    Mixin for common item properties.
    """

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

    @classmethod
    def _search_string(cls):
        return cls.notes

    id = Column(Integer, primary_key=True)
    notes = Column(String, nullable=False, default='')
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    modified_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    def to_json(self):
        def _value(value):
            if hasattr(value, 'isoformat'):  # datetime
                return value.isoformat()
            return value

        return {c.name: _value(getattr(self, c.name)) for c in self.__table__.columns if not c.name.startswith('_')}

    def from_json(self, data):
        for k, v in data.items():
            setattr(self, k, v)

    @hybrid_property
    def summary(self):
        """
        Used to display a short hand description of this record.
        """
        return self.notes
