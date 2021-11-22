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
'''
Jinja2 Tool for CherryPy.
'''
import cherrypy


def jinja2_handler(*args, **kwargs):
    request = cherrypy.serving.request
    # Get more variables
    values = dict()
    if request._jinja2_extra_processor:
        values.update(request._jinja2_extra_processor(request))
    # Call handler
    values.update(request._jinja2_inner_handler(*args, **kwargs))
    # Convert data to jinja2
    template = request._jinja2_inner_template
    return template.render(values)


def jinja2_out(env, template, extra_processor=None, debug=False):
    request = cherrypy.serving.request
    # request.handler may be set to None by e.g. the caching tool
    # to signal to all components that a response body has already
    # been attached, in which case we don't need to wrap anything.
    if request.handler is None:
        return

    if debug:
        cherrypy.log('Replacing %s with Jinja2 handler' % request.handler,
                     'TOOLS.JINJA2')
    request._jinja2_inner_handler = request.handler
    request._jinja2_inner_template = env.get_template(template)
    request._jinja2_extra_processor = extra_processor
    request.handler = jinja2_handler


cherrypy.tools.jinja2 = cherrypy.Tool(
    'before_handler', jinja2_out, priority=30)
