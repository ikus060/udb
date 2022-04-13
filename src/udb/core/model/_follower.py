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
from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import ForeignKey, Index
from sqlalchemy.sql.sqltypes import Integer

import udb.tools.db  # noqa: import cherrypy.tools.db

from ._user import User

Base = cherrypy.tools.db.get_base()


class Follower(Base):
    __tablename__ = 'follower'

    id = Column(Integer, primary_key=True)
    model = Column(String, nullable=False)
    model_id = Column(Integer, nullable=False)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    user = relationship(User)


# Create a unique index for username
Index('follower_index', Follower.model, Follower.model_id, Follower.user_id, unique=True)


class FollowerMixin:
    def add_follower(self, user, commit=True):
        assert self.id
        assert user
        if not self.is_following(user):
            f = Follower(model=self.__tablename__, model_id=self.id, user=user)
            f.add(commit=commit)

    def remove_follower(self, user):
        assert self.id
        assert user
        assert user.id
        f = Follower.query.where(
            Follower.model == self.__tablename__, Follower.model_id == self.id, Follower.user == user
        ).first()
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
        return (
            Follower.query.where(
                Follower.model == self.__tablename__, Follower.model_id == self.id, Follower.user == user
            ).first()
            is not None
        )
