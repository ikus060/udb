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

import cherrypy
from cherrypy.process.plugins import DropPrivileges
from cherrypy_foundation.logging import setup_logging

from udb.app import UdbApplication
from udb.config import parse_args


def main(args=None):
    """
    Main entry point of the web server.
    """
    # Read configuration option from arguments, configuration file or environment variable.
    cfg = parse_args(args)

    # Configure logging system
    log_level = "DEBUG" if cfg.debug else cfg.log_level
    setup_logging(log_file=cfg.log_file, log_access_file=cfg.log_access_file, level=log_level)

    # Configure web server
    cherrypy.config.update(
        {
            'server.socket_host': cfg.server_host,
            'server.socket_port': cfg.server_port,
        }
    )

    # DropPriviledge
    cherrypy.drop_privileges = DropPrivileges(cherrypy.engine, umask=cfg.umask, uid=cfg.user, gid=cfg.group)
    cherrypy.drop_privileges.subscribe()

    # start app
    cherrypy.quickstart(UdbApplication(cfg=cfg))


if __name__ == "__main__":
    main()
