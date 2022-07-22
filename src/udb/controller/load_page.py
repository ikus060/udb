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


import csv
import os
import shutil
import tempfile

import cherrypy
from wtforms import validators
from wtforms.fields import FileField

from udb.controller import flash, handle_exception
from udb.core.model import DnsZone, Subnet, Vrf
from udb.tools.i18n import gettext as _

from .form import CherryForm


class LoadForm(CherryForm):
    # TODO Validate empty file
    # TODO Hint for .csv file
    # TODO Support more then subnet
    upload_file = FileField(_('CSV File'), validators=[validators.data_required()])


class LoadPage:
    def get_or_create(self, model, name):
        if not name:
            return None
        obj = model.query.filter(model.name == name).first()
        if obj is None:
            obj = model(name=name).add(commit=False)
        return obj

    def get_int(self, value):
        if not value:
            return None
        return int(value)

    @cherrypy.expose()
    @cherrypy.config(**{'server.max_request_body_size': 0})
    @cherrypy.tools.jinja2(template=['load.html'])
    def index(self, **kwargs):
        form = LoadForm()
        if form.validate_on_submit():
            reader = None
            row = None
            try:
                # Write attachment to a temporary file on filesystem
                (fd, temp_filename) = tempfile.mkstemp(
                    prefix='ekwos-upload-', suffix=os.path.basename(form.upload_file.data.filename)
                )
                with open(fd, 'wb') as f:
                    shutil.copyfileobj(form.upload_file.data.file, f, length=65365)

                # Read file as CSV
                with open(temp_filename, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        vrf = self.get_or_create(Vrf, row.get('VRF'))
                        zone = self.get_or_create(DnsZone, row.get('TLD'))
                        Subnet(
                            ip_cidr=row.get('IPv6'),
                            name=row.get('Name'),
                            vrf=vrf,
                            l3vni=self.get_int(row.get('L3VNI')),
                            l2vni=self.get_int(row.get('L2VNI')),
                            vlan=self.get_int(row.get('VLAN')),
                            notes=row.get('Description'),
                            dnszones=[zone] if zone else [],
                        ).add(commit=False)
                        cherrypy.tools.db.get_session().flush()
                cherrypy.tools.db.get_session().commit()
                flash(_('CSV File imported with success !'))
            except Exception as e:
                msg = _('Fail to process the given CSV file.')
                if reader.line_num:
                    msg += _(' Line: ') + str(reader.line_num)
                if row:
                    msg += _(' Row: ') + str(row)
                flash(msg, level='error')
                handle_exception(e)

        return {'form': form}
