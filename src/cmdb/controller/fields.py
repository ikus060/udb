# -*- coding: utf-8 -*-
# cmdb, A web interface to manage IT network CMDB
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
from cmdb.core.model import User
from cmdb.tools.i18n import gettext as _
from wtforms.fields.core import SelectField


def objid(value):
    if value is None or value == 'None':
        return None
    return int(value)


class UserField(SelectField):
    """
    Field to select a user.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, coerce=objid, **kwargs)

    def iter_choices(self):
        """
        Replace default implementation by returning the list of current users.
        """
        # TODO Avoid showing deleted user.
        users = User.query.all()
        yield (None, _("Not assigned"), self.data is None)
        for user in users:
            value = user.id
            label = user.fullname or user.username
            selected = self.coerce(user.id) == self.data
            yield (value, label, selected)
