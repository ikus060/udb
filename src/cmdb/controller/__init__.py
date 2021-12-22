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
import datetime
import time
from collections import namedtuple

import cherrypy
from cmdb.tools.i18n import gettext as _

FlashMessage = namedtuple('FlashMessage', ['message', 'level'])


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


def url_for(*args, **kwargs):
    """
    Generate a URL for the given endpoint, path (*args) with parameters (**kwargs)
    """
    path = ""
    for chunk in args:
        if isinstance(chunk, str):
            path += "/"
            path += chunk.rstrip("/")
        elif isinstance(chunk, int):
            path += "/"
            path += str(chunk)
        else:
            raise ValueError(
                'invalid positional arguments, url_for accept str, bytes, int: %r' % chunk)
    qs = [(k, v)
          for k, v in sorted(kwargs.items()) if v is not None]
    return cherrypy.url(path=path, qs=qs)


def lastupdated(value, now=None):
    """
    Used to format date as "Updated 10 minutes ago".

    Value could be a RdiffTime or an epoch as int.
    """
    if not value:
        return ""
    now = datetime.datetime.fromtimestamp(time.time())
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
        'url_for': url_for,
    }
    if hasattr(cherrypy.serving.request, 'login'):
        values['username'] = cherrypy.serving.request.login
    if hasattr(cherrypy.serving.request, 'currentuser'):
        values['currentuser'] = cherrypy.serving.request.currentuser
    return values
