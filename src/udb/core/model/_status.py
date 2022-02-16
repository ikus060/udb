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


from sqlalchemy import Column, String
from sqlalchemy.orm import validates


class StatusMixing(object):
    """
    Mixin to support soft delete (enabled, disable, deleted)
    """
    STATUS_ENABLED = 'enabled'
    STATUS_DISABLED = 'disabled'
    STATUS_DELETED = 'deleted'
    STATUS = [STATUS_ENABLED, STATUS_DISABLED, STATUS_DELETED]

    status = Column(String, default=STATUS_ENABLED)

    @validates('status')
    def validate_status(self, key, value):
        if value not in StatusMixing.STATUS:
            raise ValueError(value)
        return value
