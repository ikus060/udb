# udb, A web interface to manage IT network
# Copyright (C) 2022-2025 IKUS Software inc.
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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from functools import wraps

from sqlalchemy import inspect
from sqlalchemy.orm import declarative_mixin


class hybridmethod(object):
    """
    Define hybrid method to works from both the class and an instance.
    """

    def __init__(self, func):
        self.func = func

    def __get__(self, obj, cls):
        context = obj if obj is not None else cls

        @wraps(self.func)
        def hybrid(*args, **kw):
            return self.func(context, *args, **kw)

        # optional, mimic methods some more
        hybrid.__func__ = hybrid.im_func = self.func
        hybrid.__self__ = hybrid.im_self = context

        return hybrid


@declarative_mixin
class UrlMixin(object):
    """
    Mixin for url_for().
    """

    @hybridmethod
    def __url_for__(owner):
        """
        Used by `url_for()` to build a URL to this model.
        """
        if isinstance(owner, type):
            # called via the class
            return owner.__name__.lower()
        else:
            # called via an instance
            base = owner.__class__.__name__.lower()
            key_name = inspect(owner.__class__).primary_key[0].name
            key = getattr(owner, key_name)
            return f"{base}/{key}"
