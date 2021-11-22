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
from collections import namedtuple

import cherrypy

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


def url_for(endpoint, *args, **kwargs):
    """
    Generate a URL for the given endpoint, path (*args) with parameters (**kwargs)
    """
    path = "/" + endpoint.strip("/")
    for chunk in args:
        if not chunk:
            continue
        elif chunk and isinstance(chunk, str):
            path += "/"
            path += chunk.rstrip("/")
        else:
            raise ValueError(
                'invalid positional arguments, url_for accept str, bytes or RepoPath: %r' % chunk)
    qs = [(k, v)
          for k, v in sorted(kwargs.items()) if v is not None]
    return cherrypy.url(path=path, qs=qs)


def template_processor(request):
    app = cherrypy.tree.apps[''].root
    values = {
        'header_name': app.cfg.header_name,
        'footer_url': app.cfg.footer_url,
        'footer_name': app.cfg.footer_name,
        'get_flashed_messages': get_flashed_messages,
        'url_for': url_for,
    }
    if hasattr(cherrypy, 'session'):
        values['username'] = cherrypy.session.get('_cp_username')
    return values
