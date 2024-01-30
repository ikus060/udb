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


from collections import namedtuple

import cherrypy

from udb.controller import url_for, verify_perm
from udb.controller.api import checkpassword
from udb.controller.common_page import CommonApi
from udb.core.model import Deployment, DnsRecord, DnsZone, Environment, User

TOKEN_USERNAME = 'token'


def checkpassword_or_token(realm, username, password):
    """
    Accept username & password authentication Or deployment token.
    """
    valid = checkpassword(realm, username, password)
    if not valid:
        # Check if token is valid for the deployment ID
        deployment_id = cherrypy.request.params.get('id', None)
        return Deployment.query.filter(Deployment.id == deployment_id, Deployment.token == password).count() >= 1
    return valid


DeploymentRow = namedtuple(
    'DeploymentRow', ['id', 'state', 'environment', 'created_at', 'change_count', 'owner', 'url']
)

ChangeRow = namedtuple(
    'ChangeRow', ['model_id', 'summary', 'model_name', 'author', 'date', 'type', 'body', 'changes', 'url']
)


class DeploymentPage:
    @cherrypy.expose()
    @cherrypy.tools.jinja2(template=['deployment/list.html'])
    def index(self):
        return {}

    def _get_or_404(self, id):
        """
        Get object with the given key or raise a 404 error.
        """
        deployment = Deployment.query.filter(Deployment.id == id).first()
        if not deployment:
            raise cherrypy.HTTPError(404)
        return deployment

    @cherrypy.expose()
    @cherrypy.tools.json_out()
    def changes_json(self, id, **kwargs):
        """
        Return list of changes for this deployment.
        """
        deployment = self._get_or_404(id)
        return {
            'data': [
                ChangeRow(
                    model_id=obj.model_id,
                    summary=obj.get_summary(),
                    model_name=obj.model_name,
                    author=obj.author_name,
                    date=obj.date.isoformat(),
                    type=obj.type,
                    body=obj.body,
                    changes=obj.changes,
                    url=url_for(obj.model_name, obj.model_id, 'edit', relative='server'),
                )
                for obj in deployment.changes
            ]
        }

    @cherrypy.expose()
    @cherrypy.tools.json_out()
    def deployments_json(self, **kwargs):
        """
        Return list of deployment.
        """
        obj_list = (
            Deployment.session.query(
                Deployment.id,
                Deployment.state,
                Environment.name.label('environment'),
                Deployment.change_count,
                Deployment.created_at,
                User.summary.label('owner'),
            )
            .outerjoin(Deployment.owner)
            .outerjoin(Deployment.environment)
            .order_by(Deployment.id.desc())
            .limit(10)
            .all()
        )
        return {
            'data': [
                DeploymentRow(
                    id=obj.id,
                    state=obj.state,
                    environment=obj.environment,
                    change_count=obj.change_count,
                    created_at=obj.created_at.isoformat(),
                    owner=obj.owner,
                    url=url_for('deployment', obj.id, 'view'),
                )
                for obj in obj_list
            ]
        }

    @cherrypy.expose()
    @cherrypy.tools.json_out()
    def output_json(self, id, **kwargs):
        """
        Called by Web interface to refresh the ouput view at regular interval.
        Return the current state and the full console log.
        """
        deployment = self._get_or_404(id)
        return {
            'state': deployment.state,
            'output': deployment.output,
        }

    @cherrypy.expose
    @cherrypy.tools.jinja2(template='deployment/view.html')
    def view(self, id, **kwargs):
        deployment = self._get_or_404(id)
        return {
            'deployment': deployment,
        }

    @cherrypy.expose
    @cherrypy.tools.jinja2(template='deployment/changes.html')
    def changes(self, id, **kwargs):
        deployment = self._get_or_404(id)
        return {
            'deployment': deployment,
        }


DeploymentPage._cp_dispatch = cherrypy.popargs('id', handler=DeploymentPage())


@cherrypy.popargs('id')  # Popargs to support zonefile and data_json
class DeploymentApi(CommonApi):
    """
    API To access deployment data.
    """

    def __init__(self):
        super().__init__(Deployment, list_perm=User.PERM_NETWORK_LIST, edit_perm=-1, new_perm=-1)
        setattr(self, 'data.json', self.data_json)

    @cherrypy.expose()
    @cherrypy.tools.auth_basic(on=True, checkpassword=checkpassword_or_token)
    def data_json(self, id=None, **kwargs):
        """
        Return deployment data as Json.
        """
        # Check role
        verify_perm(self.list_perm)
        # Get object
        deployment = self._get_or_404(id)
        # Return data
        return deployment.data

    @cherrypy.expose()
    @cherrypy.tools.auth_basic(on=True, checkpassword=checkpassword_or_token)
    @cherrypy.tools.jinja2(template=['dnszone/zone.j2'])
    @cherrypy.tools.json_out(on=False)
    @cherrypy.tools.response_headers(headers=[('Content-Type', 'text/plain')])
    def zonefile(self, id=None, name=None, **kwargs):
        """
        Generate a DNS Zone file from deployment data.
        """
        deployment = self._get_or_404(id)

        # Return 404 is dnsrecord is not part of this deployment.
        dnsrecords = deployment.data.get('dnsrecord', None)
        if dnsrecords is None:
            raise cherrypy.HTTPError(404, "Wrong deployment type")

        # Return 404 if name is not a Zone
        zone = DnsZone.query.filter(DnsZone.name == name).first()
        if zone is None:
            raise cherrypy.HTTPError(404, "Zone name not found")

        # Filter out records base on zone name
        dnsrecords = [
            r for r in dnsrecords if r.get('name' if r.get('type', None) != 'PTR' else 'value', '').endswith(name)
        ]

        # Then simply sort the dnsrecords
        # Make sure SOA record are first.
        return {'dnsrecords': dnsrecords, 'dnsrecord_sort_key': DnsRecord.dnsrecord_sort_key}
