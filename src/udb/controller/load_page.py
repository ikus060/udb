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
from wtforms.fields import FileField, SelectField

from udb.controller import flash, handle_exception
from udb.core.model import DnsRecord, DnsZone, Subnet, Vrf
from udb.tools.i18n import gettext_lazy as _

from .form import CherryForm


class LoadForm(CherryForm):
    type_file = SelectField(
        _('Type'),
        choices=[('subnet', _('Subnet file')), ('dnsrecord', 'DNS Zone file')],
    )
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
            obj = model(name=name).add()
        return obj

    def get_int(self, value):
        if not value:
            return None
        return int(value)

    def _import_subnet(self, filename):
        reader = None
        row = None
        try:
            # Read file as CSV
            with open(filename, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    vrf = self.get_or_create(Vrf, row.get('VRF'))
                    zone = self.get_or_create(DnsZone, row.get('TLD'))
                    ranges = [row.get('IPv6')]
                    if row.get('IPv4'):
                        ranges.extend(row.get('IPv4').split(' '))
                    Subnet(
                        ranges=ranges,
                        name=row.get('Name'),
                        vrf=vrf,
                        l3vni=self.get_int(row.get('L3VNI')),
                        l2vni=self.get_int(row.get('L2VNI')),
                        vlan=self.get_int(row.get('VLAN')),
                        notes=row.get('Description'),
                        dnszones=[zone] if zone else [],
                    ).add().flush()
            cherrypy.tools.db.get_session().commit()
        except Exception as e:
            msg = _('Fail to process the given file.')
            if reader.line_num:
                msg += _(' Line: ') + str(reader.line_num)
            if row:
                msg += _(' Row: ') + str(row)
            if isinstance(e, ValueError) and len(e.args) == 2:
                msg += ' ' + str(e.args[0]) + ' ' + str(e.args[1])
            else:
                msg += str(e)
            raise ValueError(msg)

    def _import_dnsrecord(self, filename):
        line_num = 0
        row = None
        # Add all record.
        try:
            # Read file as CSV
            with open(filename, 'r') as f:
                for line in f:
                    line_num += 1
                    # Skip empty line or comments.
                    if not line or line.startswith(';;'):
                        continue
                    # Parse line
                    row = line.strip('\r\n').replace('\t', ' ').split(maxsplit=4)
                    name = row[0].strip('.')
                    ttl = row[1]
                    type = row[3]
                    value = row[4]
                    if type in ['CNAME', 'PTR', 'NS']:
                        value = value.strip('.')
                    r = DnsRecord(name=name, ttl=ttl, type=type, value=value)
                    r.add().flush()
            cherrypy.tools.db.get_session().commit()
        except Exception as e:
            msg = _('Fail to process the given file.')
            if line_num:
                msg += _(' Line: ') + str(line_num)
            if row:
                msg += _(' Row: ') + str(row)
            if isinstance(e, ValueError) and len(e.args) == 2:
                msg += ' ' + str(e.args[0]) + ' ' + str(e.args[1])
            else:
                msg += str(e)
            raise Exception(msg)

    @cherrypy.expose()
    @cherrypy.config(**{'server.max_request_body_size': 0})
    @cherrypy.tools.jinja2(template=['load.html'])
    def index(self, **kwargs):
        form = LoadForm()
        if form.validate_on_submit():

            try:
                # Write attachment to a temporary file on filesystem
                (fd, temp_filename) = tempfile.mkstemp(
                    prefix='ekwos-upload-', suffix=os.path.basename(form.upload_file.data.filename)
                )
                with open(fd, 'wb') as f:
                    shutil.copyfileobj(form.upload_file.data.file, f, length=65365)

                # Import accoridng to file type
                if form.type_file.data == 'subnet':
                    self._import_subnet(temp_filename)
                elif form.type_file.data == 'dnsrecord':
                    self._import_dnsrecord(temp_filename)
                else:
                    raise ValueError('invalid type')

                flash(_('CSV File imported with success !'))
            except Exception as e:
                handle_exception(e)

        return {'form': form}
