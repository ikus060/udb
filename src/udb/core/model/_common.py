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

from sqlalchemy import Column, ForeignKey, Integer, String, func, inspect
from sqlalchemy.orm import declarative_mixin, declared_attr, relationship

from ._timestamp import Timestamp
from ._user import User


@declarative_mixin
class CommonMixin(object):
    """
    Mixin for common item properties.
    """

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    id = Column(Integer, primary_key=True)
    notes = Column(String, nullable=False, default='')
    created_at = Column(Timestamp(timezone=True), nullable=False, server_default=func.now())
    modified_at = Column(Timestamp(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    @declared_attr
    def owner_id(cls):
        return Column(Integer, ForeignKey('user.id'))

    @declared_attr
    def owner(cls):
        return relationship(User, lazy=True, active_history=True)

    def attr_has_changes(self, *attrs):
        """
        Return true if any of the given attributes of the model has changed.
        """
        state = inspect(self)
        for key in attrs:
            attr_state = state.attrs[key]
            hist = attr_state.history
            if hist.has_changes():
                return True
        return False

    def attr_revert_changes(self, *attrs):
        """
        Used to clear the state history of an attribute.
        """
        state = inspect(self)
        for key in attrs:
            if key in state.dict:
                del state.dict['vrf']
