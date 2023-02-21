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
import datetime
import logging
import re
import time
from collections import namedtuple

import cherrypy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.inspection import inspect

from udb.tools.i18n import gettext as _

logger = logging.getLogger(__name__)

FlashMessage = namedtuple('FlashMessage', ['message', 'level'])

# Capture epoch time to invalidate cache of static file.
_cache_invalidate = int(time.time())


def flash(message, level='info'):
    """
    Add a flashin message to the session.
    """
    assert message
    assert level in ['info', 'error', 'warning', 'success']
    if 'flash' not in cherrypy.session:  # @UndefinedVariable
        cherrypy.session['flash'] = []  # @UndefinedVariable
    flash_message = FlashMessage(message, level)
    cherrypy.session['flash'].append(flash_message)


def get_flashed_messages():
    if 'flash' in cherrypy.session:  # @UndefinedVariable
        messages = cherrypy.session['flash']  # @UndefinedVariable
        del cherrypy.session['flash']  # @UndefinedVariable
        return messages
    return []


def url_for(*args, relative=None, **kwargs):
    """
    Generate a URL for the given endpoint, path (*args) with parameters (**kwargs)

    If `relative` is None or not provided, default to absolute
    path. If False, the output will be an absolute URL (including
    the scheme, host, vhost, and script_name). If True, the output
    will instead be a URL that is relative to the
    current request path, perhaps including '..' atoms. If relative is
    the string 'server', the output will instead be a URL that is
    relative to the server root; i.e., it will start with a slash.
    """
    path = ""
    for chunk in args:
        if isinstance(chunk, str):
            if not chunk.startswith('.'):
                path += "/"
            path += chunk.rstrip("/")
        elif isinstance(chunk, int):
            path += "/"
            path += str(chunk)
        elif hasattr(chunk, 'model_name') and hasattr(chunk, 'model_id'):
            path += "/%s/%s" % (chunk.model_name, chunk.model_id)
        elif hasattr(chunk, '_sa_instance_state'):
            # SQLAlchemy object
            base = chunk.__class__.__name__.lower()
            key_name = inspect(chunk.__class__).primary_key[0].name
            key = getattr(chunk, key_name)
            path += "/%s/%s" % (base, key)
        elif hasattr(chunk, '_sa_registry'):
            # SQLAlchemy model
            path += "/"
            path += chunk.__name__.lower()
            if len(args) == 1:
                path += "/"
        else:
            raise ValueError('invalid positional arguments, url_for accept str, bytes, int: %r' % chunk)
    # When path is empty, we are browsing the same page.
    # Let keep the original query_string to avoid loosing it.
    if path == "":
        params = cherrypy.request.params.copy()
        params.update(kwargs)
        qs = [(k, v) for k, v in sorted(params.items()) if v is not None]
    else:
        qs = [(k, v) for k, v in sorted(kwargs.items()) if v is not None]
    # Outside a request, use the external_url as base if defined
    base = None
    if not cherrypy.request.app:
        app = cherrypy.tree.apps[''].root
        base = app.cfg.external_url
    return cherrypy.url(path=path, qs=qs, relative=relative, base=base)


def verify_role(role):
    """
    Verify if the current user has the required role.
    """
    user = cherrypy.serving.request.currentuser
    if user is None or not user.has_role(role):
        raise cherrypy.HTTPError(403, 'Insufficient privileges')


def lastupdated(value, now=None):
    """
    Used to format date as "Updated 10 minutes ago".

    Value could be a RdiffTime or an epoch as int.
    """
    if not value:
        return ""
    if value.tzinfo:
        now = datetime.datetime.now(datetime.timezone.utc)
    else:
        now = datetime.datetime.now()
    delta = now - value
    if delta.days > 365:
        return _('%d years ago') % (delta.days / 365)
    if delta.days > 60:
        return _('%d months ago') % (delta.days / 30)
    if delta.days > 7:
        return _('%d weeks ago') % (delta.days / 7)
    elif delta.days > 1:
        return _('%d days ago') % delta.days
    elif delta.seconds > 3600:
        return _('%d hours ago') % (delta.seconds / 3600)
    elif delta.seconds > 60:
        return _('%d minutes ago') % (delta.seconds / 60)
    return _('%d seconds ago') % delta.seconds


def template_processor(request):
    app = cherrypy.tree.apps[''].root
    values = {
        'header_name': app.cfg.header_name,
        'footer_url': app.cfg.footer_url,
        'footer_name': app.cfg.footer_name,
        'get_flashed_messages': get_flashed_messages,
        'current_url': cherrypy.url(path=cherrypy.request.path_info),
        'cache_invalidate': _cache_invalidate,
    }
    if hasattr(cherrypy.serving.request, 'login'):
        values['username'] = cherrypy.serving.request.login
    if hasattr(cherrypy.serving.request, 'currentuser'):
        values['currentuser'] = cherrypy.serving.request.currentuser
    return values


def handle_exception(e, form=None):
    cherrypy.tools.db.get_session().rollback()
    if isinstance(e, ValueError):
        # For value error, repport the invalidvalue either as flash message or form error.
        if form and len(e.args) == 2 and getattr(form, e.args[0], None):
            getattr(form, e.args[0]).errors.append(e.args[1])
        elif len(e.args) == 2:
            flash(_('Invalid value: %s') % e.args[1], level='error')
        else:
            flash(_('Invalid value: %s') % e, level='error')
    elif isinstance(e, IntegrityError) and 'unique' in str(e.orig).lower():
        # For Unique constrain violation, we try to identify the field causing the problem to properly
        # attach the error to the fields. If the fields cannot be found using the constrain
        # name, we simply show a flash error message.
        msg = _('A record already exists in database with the same value.')
        # Postgresql: duplicate key value violates unique constraint "subnet_name_key"\nDETAIL:  Key (name)=() already exists.\n
        # SQLite: UNIQUE constrain: subnet.name
        m = re.search(r'Key \((.*?)\)', str(e.orig)) or re.search(r'.*\.(.*)', str(e.orig))
        if m and form and getattr(form, m[1], None):
            getattr(form, m[1]).errors.append(msg)
        elif m:
            # Or repport error as flash.
            flash(msg + _(' Field(s): ') + m[1], level='error')
        else:
            flash(msg + _(' Index: ') + str(e.orig), level='error')
    else:
        flash(_('Database error: %s') % e, level='error')
        logger.warning('database error', exc_info=1)
