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

import logging
import sys

import cherrypy

from udb.app import Root
from udb.config import parse_args


def _setup_logging(log_file, log_access_file, level):
    """
    Configure the logging system for cherrypy.
    """
    assert isinstance(logging.getLevelName(level), int)

    def remove_cherrypy_date(record):
        """Remove the leading date for cherrypy error."""
        if record.name.startswith('cherrypy.error'):
            record.msg = record.msg[23:].strip()
        return True

    def add_ip(record):
        """Add request IP to record."""
        if hasattr(cherrypy, 'serving'):
            request = cherrypy.serving.request
            remote = request.remote
            record.ip = remote.name or remote.ip
            # If the request was forwarded by a reverse proxy
            if 'X-Forwarded-For' in request.headers:
                record.ip = request.headers['X-Forwarded-For']
        return True

    def add_username(record):
        """Add current username to record."""
        record.user = cherrypy.request and cherrypy.request.login or "anonymous"
        return True

    cherrypy.config.update({'log.screen': False, 'log.access_file': '', 'log.error_file': ''})
    cherrypy.engine.unsubscribe('graceful', cherrypy.log.reopen_files)

    # Configure root logger
    logger = logging.getLogger('')
    logger.level = logging.getLevelName(level)
    if log_file:
        print("continue logging to %s" % log_file)
        default_handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=10485760, backupCount=20)
    else:
        default_handler = logging.StreamHandler(sys.stdout)
    default_handler.addFilter(remove_cherrypy_date)
    default_handler.addFilter(add_ip)
    default_handler.addFilter(add_username)
    default_handler.setFormatter(
        logging.Formatter("[%(asctime)s][%(levelname)-7s][%(ip)s][%(user)s][%(threadName)s][%(name)s] %(message)s")
    )
    logger.addHandler(default_handler)

    # Configure cherrypy access logger
    cherrypy_access = logging.getLogger('cherrypy.access')
    cherrypy_access.propagate = False
    if log_access_file:
        handler = logging.handlers.RotatingFileHandler(log_access_file, maxBytes=10485760, backupCount=20)
        cherrypy_access.addHandler(handler)

    # Configure cherrypy error logger
    cherrypy_error = logging.getLogger('cherrypy.error')
    cherrypy_error.propagate = False
    cherrypy_error.addHandler(default_handler)


def main(args=None):
    """
    Main entry point of the web server.
    """
    # Read configuration option from arguments, configuration file or environment variable.
    cfg = parse_args(args)

    # Configure logging system
    log_level = "DEBUG" if cfg.debug else cfg.log_level
    _setup_logging(log_file=cfg.log_file, log_access_file=cfg.log_access_file, level=log_level)

    # Configure web server
    environment = 'debug' if cfg.debug else 'production'
    cherrypy.config.environments['debug'] = {
        'engine.autoreload.on': True,
        'checker.on': False,
        'tools.log_headers.on': True,
        'request.show_tracebacks': True,
        'request.show_mismatched_params': True,
    }
    cherrypy.config.update(
        {
            'server.socket_host': cfg.server_host,
            'server.socket_port': cfg.server_port,
            'environment': environment,
        }
    )

    # start app
    cherrypy.quickstart(Root(cfg=cfg), '/')


if __name__ == "__main__":
    main()
