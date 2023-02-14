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


import cherrypy

from udb.controller import lastupdated, url_for, verify_role
from udb.controller.api import checkpassword
from udb.controller.common_page import CommonApi
from udb.core.model import Deployment, DnsRecord, DnsZone, Environment, Message, User

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


class DeploymentPage:
    @cherrypy.expose()
    @cherrypy.tools.jinja2(template=['deploy/list.html'])
    def index(self):
        verify_role(User.ROLE_ADMIN)
        return {}

    @cherrypy.expose()
    @cherrypy.tools.json_out()
    def changes_json(self, id, **kwargs):
        """
        Return list of changes since last deployment.
        """
        verify_role(User.ROLE_ADMIN)
        # List all activities by dates
        deployment = Deployment.query.filter(Deployment.id == id).first()
        if not deployment:
            raise cherrypy.HTTPError(404)

        # Query list of changes
        q = Message.query.filter(
            Message.model_name == deployment.environment.model_name,
            Message.type.in_([Message.TYPE_NEW, Message.TYPE_DIRTY]),
        )
        if deployment.start_id:
            q = q.filter(Message.id >= deployment.start_id)
        if deployment.end_id:
            q = q.filter(Message.id < deployment.end_id)
        obj_list = q.order_by(Message.id.desc()).limit(100).all()

        return {
            'data': [
                dict(
                    obj.to_json(),
                    **{
                        'url': url_for(obj.model_object, 'edit'),
                        'summary': obj.summary,
                        'author_name': obj.author_name,
                        'date_lastupdated': lastupdated(obj.date),
                    }
                )
                for obj in obj_list
            ]
        }

    @cherrypy.expose()
    @cherrypy.tools.json_out()
    def deployments_json(self, **kwargs):
        """
        Return list of deployment.
        """
        verify_role(User.ROLE_ADMIN)
        obj_list = (
            Deployment.session.query(
                Deployment.id,
                Environment.name.label('environment'),
                Deployment.change_count,
                Deployment.created_at,
                Deployment.state,
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
                dict(
                    obj,
                    **{
                        'created_at': obj.created_at.isoformat(),
                        'url': url_for('deployment', obj.id, 'view'),
                    }
                )
                for obj in obj_list
            ]
        }

    @cherrypy.expose()
    @cherrypy.tools.json_out()
    def output_json(self, id, **kwargs):
        """
        Called by Web interface to refresh the ouput view at regular interval.
        """
        verify_role(User.ROLE_ADMIN)
        # Return Not found if object doesn't exists
        deployment = Deployment.query.filter(Deployment.id == id).first()
        if not deployment:
            raise cherrypy.HTTPError(404)
        return {
            'state': deployment.state,
            'output': deployment.output,
        }

    @cherrypy.expose
    @cherrypy.tools.jinja2(template='deploy/view.html')
    def view(self, id, **kwargs):
        verify_role(User.ROLE_ADMIN)
        # Return Not found if object doesn't exists
        deployment = Deployment.query.filter(Deployment.id == id).first()
        if not deployment:
            raise cherrypy.HTTPError(404)
        # Return object form
        return {
            'deployment': deployment,
        }


DeploymentPage._cp_dispatch = cherrypy.popargs('id', handler=DeploymentPage())


class DeploymentApi(CommonApi):
    """
    API To access deployment data.
    """

    def __init__(self):
        super().__init__(Deployment, list_role=User.ROLE_ADMIN, edit_role=-1)

    @cherrypy.expose()
    @cherrypy.tools.auth_basic(on=True, checkpassword=checkpassword_or_token)
    def data_json(self, id=None, **kwargs):
        """
        Return deployment data as Json.
        """
        # Check role
        verify_role(self.list_role)
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


DeploymentApi._cp_dispatch = cherrypy.popargs('id', handler=DeploymentApi())
