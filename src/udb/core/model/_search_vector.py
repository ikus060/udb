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

from sqlalchemy import Column, Computed, Index
from sqlalchemy.orm import declared_attr, deferred
from sqlalchemy.sql.functions import func

from ._tsvector import TSVectorType


class SearchableMixing(object):
    """
    Searchable mixin to support tsvector.
    """

    @declared_attr
    def _search_vector(cls):
        return deferred(
            Column(
                TSVectorType,
                Computed(
                    func.to_tsvector('english', cls._search_string()),
                    persisted=True,
                ),
            )
        )

    @declared_attr
    def __table_args__(cls):
        return (Index('idx_%s_search_vector' % cls.__tablename__, '_search_vector', postgresql_using='gin'),)

    @classmethod
    def _search_string(cls):
        raise NotImplementedError()
