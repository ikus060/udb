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
import inspect

import cherrypy

from . import _bool_or  # noqa
from . import _group_concat  # noqa
from . import _least  # noqa
from ._deployment import Deployment, Environment  # noqa
from ._dhcprecord import DhcpRecord  # noqa
from ._dnsrecord import DnsRecord  # noqa
from ._dnszone import DnsZone  # noqa
from ._follower import Follower  # noqa
from ._ip import Ip  # noqa
from ._mac import Mac  # noqa
from ._message import Message  # noqa
from ._rule import Rule, RuleError  # noqa
from ._subnet import Subnet, SubnetRange  # noqa
from ._user import User  # noqa
from ._vrf import Vrf  # noqa

Base = cherrypy.tools.db.get_base()

# Build list of model with 'messages' attributes
all_models = [value for value in locals().values() if inspect.isclass(value) and hasattr(value, '__tablename__')]

# Build list of model with 'followers' attributes
followable_models = [
    value
    for unused, value in locals().items()
    if inspect.isclass(value) and hasattr(value, 'followers') and hasattr(value, '__tablename__')
]
followable_model_name = [value.__tablename__ for value in followable_models]

# Build list of model with 'messages' attributes
auditable_models = [
    value
    for unused, value in locals().items()
    if inspect.isclass(value) and hasattr(value, 'messages') and hasattr(value, '__tablename__')
]

# Build list of searchable model with `search_string` attribute
searchable_models = [
    value
    for unused, value in locals().items()
    if inspect.isclass(value)
    and hasattr(value, 'search_string')
    and hasattr(value, 'summary')
    and hasattr(value, '__tablename__')
]
