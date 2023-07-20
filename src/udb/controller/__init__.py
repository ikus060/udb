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
import logging
import re
import time
from collections import namedtuple

import cherrypy
from markupsafe import Markup
from sqlalchemy.exc import IntegrityError
from sqlalchemy.inspection import inspect

import udb
from udb.tools.i18n import get_translation
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
    # Support Markup and string
    if hasattr(message, '__html__'):
        flash_message = FlashMessage(message, level)
    else:
        flash_message = FlashMessage(str(message), level)
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


def verify_perm(perm):
    """
    Verify if the current user has the required permissions.
    """
    user = cherrypy.serving.request.currentuser
    if user is None or not user.has_permissions(perm):
        raise cherrypy.HTTPError(403, 'Insufficient privileges')


def template_processor(request):
    app = cherrypy.tree.apps[''].root
    values = {
        'lang': str(get_translation().locale),
        'header_name': app.cfg.header_name,
        'footer_url': app.cfg.footer_url,
        'footer_name': app.cfg.footer_name,
        'get_flashed_messages': get_flashed_messages,
        'current_url': cherrypy.url(path=cherrypy.request.path_info),
        'cache_invalidate': _cache_invalidate,
        'version': udb.__version__,
    }
    if hasattr(cherrypy.serving.request, 'login'):
        values['username'] = cherrypy.serving.request.login
    if hasattr(cherrypy.serving.request, 'currentuser'):
        values['currentuser'] = cherrypy.serving.request.currentuser
    return values


def handle_exception(e, form=None):
    cherrypy.tools.db.get_session().rollback()
    if isinstance(e, ValueError):
        # ValueError are raised by SQLalchemy custom validation
        # For value error, repport the invalid value either as flash message or form error.
        if form and len(e.args) == 2 and getattr(form, e.args[0], None):
            getattr(form, e.args[0]).errors.append(e.args[1])
        elif len(e.args) == 2:
            flash(_('Invalid value: %s') % e.args[1], level='error')
        else:
            flash(_('Invalid value: %s') % e, level='error')
    elif isinstance(e, IntegrityError):
        # Integrity error are raised by Database
        _handle_integrity_error(e, form)
    else:
        flash(_('Database error: %s') % e, level='error')
        logger.warning('database error', exc_info=1)


def _handle_integrity_error(e, form=None):
    """
    This implementation lookup the metadata to find the corresponding
    constraints and retrieve additional information to better help the end-user.
    """
    error = str(e.orig)
    ctx = _get_context(e)

    if 'unique' in error.lower():
        # For Unique constrain violation, we try to identify the field causing the problem to properly
        # attach the error to the fields. If the fields cannot be found using the constrain
        # name, we simply show a flash error message.
        description = _('A record already exists in database with the same value.')
        field = None
        other = None

        # Extract the constraint name for Postgresql and SQLite
        # Postgresql: duplicate key value violates unique constraint "subnet_name_key"\nDETAIL:  Key (name)=() already exists.\n
        # SQLite: UNIQUE constrain: subnet.name
        # SQLite: UNIQUE constraint failed: index "dnszone_name_index"
        constraint_match = (
            re.search(r'unique constraint "([^"]+)"', error)
            or re.search(r': (.+\..+)', error)
            or re.search(r": index '([^']+)'", error)
        )
        if constraint_match:
            constraint = _find_constraint(constraint_match[1])
            if constraint:
                description = constraint.info.get('description', description)
                field = constraint.info.get('field', None)
                find_other = constraint.info.get('other', None)
                if find_other:
                    try:
                        other = find_other(ctx)
                    except Exception:
                        pass
        else:
            field_match = re.search(r'Key \((.+?)\)', error) or re.search(r'.+\.(.+)', error)
            if field_match:
                field = field_match[1]

    # From data collected, create an error message for the user.
    if other:
        message = Markup('%s <a href="%s">%s</a>') % (
            description,
            url_for(other, 'edit'),
            other.summary,
        )
    else:
        message = description

    if form and field in form:
        # Add message to form if field exists.
        getattr(form, field).errors.append(message)
    elif field:
        # Otherwise, repport error as flash.
        flash(message + _(' Field(s): ') + field, level='error')
    else:
        flash(message + _(' Index: ') + str(e.orig), level='error')


def _find_constraint(name):
    # Use a lookup cache to simplify the search of index and constraints.
    if not getattr(_find_constraint, '_cache', False):
        cache = {}
        metadata = cherrypy.tools.db.get_base().metadata
        for table in metadata.tables.values():
            for item in table.constraints:
                if item.name:
                    cache[item.name] = item
            for item in table.indexes:
                # Keep reference to unique index only.
                if item.unique:
                    if item.name:
                        cache[item.name] = item
                    # SQLite return <table>.<column>
                    key = ', '.join([f'{table.name}.{c.name}' for c in item.columns])
                    cache[key] = item
        _find_constraint._cache = cache

    return _find_constraint._cache.get(name, None)


def _get_context(e):

    # PostgreSQL : When using named params use it
    if isinstance(e.params, dict):
        return e.params

    # Search fields from SQL statement
    fields = []
    if e.statement.startswith('INSERT INTO'):
        match = re.match(r'INSERT INTO [^ ]+ \((.*)\) VALUES', e.statement)
        if match:
            fields = match[1].split(', ')
    elif e.statement.startswith('UPDATE'):
        fields = re.findall(r' ([^ ]+)\s?=\s?\?', e.statement)

    # Rebuild the context as dictionary
    values = e.params
    if len(fields) == len(values):
        return dict(zip(fields, values))

    return None


def validate_int(value, message=None, min=None, max=None):
    """
    Raise HTTP Error if the value is not an integer
    """
    try:
        value = int(value)
        if min and value < min:
            raise cherrypy.HTTPError(400, message)
        if max and value > max:
            raise cherrypy.HTTPError(400, message)
        return value
    except ValueError:
        raise cherrypy.HTTPError(400, message)
