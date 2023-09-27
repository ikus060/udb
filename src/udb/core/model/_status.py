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


from sqlalchemy import Column, Computed, Integer, func
from sqlalchemy.orm import declared_attr, validates


class StatusMixing(object):
    """
    Mixin to support soft delete (enabled, disable, deleted)
    """

    STATUS_ENABLED = 2
    STATUS_DISABLED = 1
    STATUS_DELETED = 0

    status = Column(Integer, default=STATUS_ENABLED, server_default=str(STATUS_ENABLED), nullable=False)

    @declared_attr
    def estatus(cls):
        """
        Create a column with real status.
        """
        status_fields = cls._estatus()
        assert status_fields
        if len(status_fields) == 1:
            return Column(Integer, Computed(status_fields[0], persisted=True))
        return Column(Integer, Computed(func.least(*status_fields), persisted=True))

    @classmethod
    def _estatus(cls):
        return [cls.status]

    @validates('status')
    def validate_status(self, key, value):
        if value not in [StatusMixing.STATUS_ENABLED, StatusMixing.STATUS_DISABLED, StatusMixing.STATUS_DELETED]:
            raise ValueError(value)
        return value
