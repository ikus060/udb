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

import inspect

import cherrypy
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import defer, undefer
from wtforms.fields import HiddenField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, ValidationError

from udb.controller import flash, lastupdated, url_for, verify_role
from udb.controller.common_page import CommonApi
from udb.core.model import Deployment, Environment, Message, User
from udb.tools.i18n import gettext as _

from .common_page import CommonPage
from .form import CherryForm, SelectObjectField


class EnvironmentForm(CherryForm):
    name = StringField(_('Environment Name'), validators=[DataRequired()], render_kw={'width': '1/2'})
    model_name = SelectField(
        _('Data Type'),
        validators=[
            DataRequired(),
            Length(max=256),
        ],
        choices=[('subnet', _('Subnets')), ('dnsrecord', _('DNS Records')), ('dhcprecord', _('DHCP Reservation'))],
        render_kw={'width': '1/2'},
    )
    script = TextAreaField(
        _('Script'),
        render_kw={
            "class": "font-monospace",
            "placeholder": _('Enter command lines used to deploy in this environment.'),
            "rows": "15",
        },
        description=_("Your shell script can use some of the predefined environment variables: %s.")
        % "UDB_USERID, UDB_USERNAME, UDB_DEPLOYMENT_ID, UDB_DEPLOYMENT_TOKEN, UDB_DEPLOYMENT_AUTH, UDB_DEPLOYMENT_MODEL_NAME, UDB_DEPLOYMENT_DATA_URL",
    )
    notes = TextAreaField(
        _('Notes'),
        default='',
        validators=[
            Length(max=256),
        ],
        render_kw={"placeholder": _("Enter details information about this DHCP Static Record")},
    )

    owner_id = SelectObjectField(
        _('Owner'),
        object_cls=User,
        object_query=lambda query: query.options(
            defer('*'),
            undefer('id'),
            undefer('fullname'),
            undefer('username'),
        ),
        default=lambda: cherrypy.serving.request.currentuser.id,
    )


class DeployForm(CherryForm):
    """
    Form used to trigger deployment in a specific environment.
    """

    last_change = HiddenField(validators=[DataRequired()])
    deploy = SubmitField(_('Deploy pending changes'))

    def validate_last_change(self, field):
        # On submit, make sure the last_change ID is identical to the default one.
        # If not, a change was saved by another user.
        if str(self.last_change.data) != str(self.last_change.default):
            raise ValidationError(
                'A recent changes was submited preventing the deployment. Please, review the latest changes befor deploying again.'
            )


class EnvironmentPage(CommonPage):
    def __init__(self):
        super().__init__(Environment, EnvironmentForm, list_role=User.ROLE_ADMIN, edit_role=User.ROLE_ADMIN)

    def _list_query(self):
        """
        Return a list of environment with number of changes to be deployed.
        """
        return Environment.query.with_entities(
            Environment.id,
            Environment.status,
            Environment.name,
            Environment.model_name,
            self._pending_changes_query(Environment)
            .with_entities(func.count(Message.id))
            .scalar_subquery()
            .label('changes_count'),
            Environment.notes,
        )

    def _pending_changes_query(self, environment):
        """
        Create a base query to list changes for a specific environment or all environment.
        """
        return Message.query.filter(
            Message.type.in_([Message.TYPE_NEW, Message.TYPE_DIRTY]),
            or_(
                Message.model_name == environment.model_name,
                and_(Message.model_name == 'environment', Message.model_id == environment.id),
            ),
            Message.id
            > func.coalesce(
                Deployment.query.with_entities(func.max(Deployment.end_id))
                .filter(Deployment.environment_id == environment.id)
                .correlate(inspect.isclass(environment) and environment)
                .scalar_subquery(),
                0,
            ),
        )

    @cherrypy.expose
    @cherrypy.tools.jinja2(template=['environment/edit.html'])
    def edit(self, key, **kwargs):
        param = super().edit(key, **kwargs)
        # Find environment or return Not Found
        environment = self._get_or_404(key)
        # Query last change id to verify if new changes was commited
        end_change = self._pending_changes_query(environment).order_by(Message.id.desc()).first()
        form = DeployForm()
        form.last_change.data = end_change.id if end_change else -1
        param['deploy_form'] = form
        return param

    @cherrypy.expose()
    def deploy(self, key, **kwargs):
        """
        Triger a deployment to specific environment.
        """
        verify_role(User.ROLE_ADMIN)
        # Find environment or return Not Found
        environment = self._get_or_404(key)
        # Identity last change
        end_change = self._pending_changes_query(environment).order_by(Message.id.desc()).first()
        form = DeployForm()
        # Store the last change ID as a reference
        form.last_change.default = end_change.id if end_change else -1
        if not form.is_submitted():
            # Expect POST
            raise cherrypy.HTTPError(405)
        if form.validate():
            currentuser = cherrypy.serving.request.currentuser
            count = self._pending_changes_query(environment).count()
            start_change = self._pending_changes_query(environment).order_by(Message.id.asc()).first()
            deployment = (
                Deployment(
                    environment_id=environment.id,
                    owner=currentuser,
                    change_count=count,
                    start_id=start_change.id if start_change else -1,
                    end_id=end_change.id if end_change else -1,
                )
                .add()
                .commit()
            )
            deployment.schedule_task(base_url=url_for('/'))
            flash('Deployment scheduled...')
            raise cherrypy.HTTPRedirect(url_for('deployment', deployment.id, 'view'))
        # Redirect user to the environment page if form is invalid.
        flash(form.error_message)
        raise cherrypy.HTTPRedirect(url_for('environment', key, 'edit'))

    @cherrypy.expose()
    @cherrypy.tools.json_out()
    def changes_json(self, key, **kwargs):
        """
        Return list of pending changes for this environment.
        """
        verify_role(User.ROLE_ADMIN)
        # Find environment or return Not Found
        environment = self._get_or_404(key)
        # List all activities by dates
        obj_list = self._pending_changes_query(environment).order_by(Message.id.desc()).limit(100).all()
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


EnvironmentPage._cp_dispatch = cherrypy.popargs('key', handler=EnvironmentPage())


class EnvironmentApi(CommonApi):
    def __init__(self):
        super().__init__(Environment, list_role=User.ROLE_ADMIN, edit_role=User.ROLE_ADMIN)