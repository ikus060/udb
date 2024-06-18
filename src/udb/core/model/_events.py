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

import cherrypy
from sqlalchemy import event

Session = cherrypy.tools.db.get_session()

_registry = {'after_flush': [], 'before_flush': []}


@event.listens_for(Session, 'after_flush', insert=True)
def _after_flush(session, flush_context):
    for obj in itertools.chain(session.new, session.dirty):
        for cls, fn in _registry['after_flush']:
            if isinstance(obj, cls):
                fn(session, flush_context, obj)


@event.listens_for(Session, 'before_flush', insert=True)
def _before_flush(session, flush_context, instances):
    for obj in itertools.chain(session.new, session.dirty):
        for cls, fn in _registry['before_flush']:
            if isinstance(obj, cls):
                fn(session, flush_context, obj)


def _listen(target, identifier, fn):
    """
    This re-implementation of sqlalchemy listener support after_flush
    and before_flush event on ORM mapper to reduce the number of loop.
    """
    assert isinstance(target, (type, tuple, list))
    assert identifier in _registry, 'invalid identifier: ' + identifier
    assert callable(fn)
    _registry[identifier].append((target, fn))


def listens_for_after_flush(target):
    def decorate(fn):
        _listen(target, 'after_flush', fn)
        return fn

    return decorate


def listens_for_before_flush(target):
    def decorate(fn):
        _listen(target, 'before_flush', fn)
        return fn

    return decorate
