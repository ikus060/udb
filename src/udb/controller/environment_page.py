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
from sqlalchemy import func
from wtforms.fields import HiddenField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, ValidationError

from udb.controller import flash, url_for, verify_perm
from udb.controller.common_page import CommonApi
from udb.core.model import Environment, Message, User
from udb.tools.i18n import gettext
from udb.tools.i18n import gettext_lazy as _

from .common_page import CommonPage
from .form import CherryForm, SelectObjectField

ChangeRow = namedtuple(
    'ChangeRow', ['model_id', 'summary', 'model_name', 'author', 'date', 'type', 'body', 'changes', 'url']
)


class EnvironmentForm(CherryForm):
    name = StringField(
        _('Environment Name'), validators=[DataRequired()], render_kw={'width': '1/2', "autofocus": True}
    )
    model_name = SelectField(
        _('Data Type'),
        validators=[
            DataRequired(),
            Length(max=256),
        ],
        render_kw={'width': '1/2'},
    )
    script = TextAreaField(
        _('Script'),
        render_kw={
            "class": "font-monospace",
            "placeholder": _('Enter command lines used to deploy in this environment.'),
            "rows": "15",
        },
    )
    notes = TextAreaField(
        _('Notes'),
        default='',
        validators=[
            Length(max=256),
        ],
        render_kw={"placeholder": _("Enter details information about this environment")},
    )

    owner_id = SelectObjectField(
        _('Owner'),
        object_cls=User,
        default=lambda: cherrypy.serving.request.currentuser.id,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model_name.choices = [
            ('subnet', gettext('Subnets')),
            ('dnsrecord', gettext('DNS Records')),
            ('dhcprecord', gettext('DHCP Reservation')),
        ]
        self.script.description = (
            _("Your shell script can use some of the predefined environment variables: %s.")
            % "UDB_USERID, UDB_USERNAME, UDB_DEPLOYMENT_ID, UDB_DEPLOYMENT_TOKEN, UDB_DEPLOYMENT_AUTH, UDB_DEPLOYMENT_MODEL_NAME, UDB_DEPLOYMENT_DATA_URL"
        )


class DeployForm(CherryForm):
    """
    Form used to trigger deployment in a specific environment.
    """

    last_change = HiddenField(validators=[DataRequired()])
    deploy = SubmitField(_('Deploy pending changes'), render_kw={"class": "btn-secondary"})

    def validate_last_change(self, field):
        # On submit, make sure the last_change ID is identical to the default one.
        # If not, a change was saved by another user.
        if str(self.last_change.data) != str(self.last_change.default):
            raise ValidationError(
                'A recent changes was submited preventing the deployment. Please, review the latest changes befor deploying again.'
            )


class EnvironmentPage(CommonPage):
    def __init__(self):
        super().__init__(
            Environment,
            EnvironmentForm,
            list_perm=User.PERM_NETWORK_LIST,
            edit_perm=User.PERM_ENVIRONMENT_EDIT,
            new_perm=User.PERM_ENVIRONMENT_EDIT,
        )

    def _list_query(self):
        """
        Return a list of environment with number of changes to be deployed.
        """
        return (
            Environment.query.with_entities(
                Environment.id,
                Environment.estatus,
                Environment.name,
                Environment.model_name,
                func.count(Environment.pending_changes).label('changes_count'),
                Environment.notes,
            )
            .outerjoin(Environment.pending_changes)
            .group_by(Environment.id)
        )

    @cherrypy.expose
    @cherrypy.tools.jinja2(template=['environment/edit.html'])
    def edit(self, key, **kwargs):
        param = super().edit(key, **kwargs)
        # Find environment or return Not Found
        environment = self._get_or_404(key)
        # Query last change id to verify if new changes was commited
        end_id = (
            Environment.query.with_entities(func.coalesce(func.max(Message.id), -1))
            .join(Environment.pending_changes)
            .filter(Environment.id == environment.id)
            .scalar()
        )
        form = DeployForm()
        form.last_change.data = end_id
        param['deploy_form'] = form
        return param

    @cherrypy.expose()
    def deploy(self, key, **kwargs):
        """
        Triger a deployment to specific environment.
        """
        verify_perm(User.PERM_NETWORK_LIST)
        # Find environment or return Not Found
        environment = self._get_or_404(key)
        # Identity last change by creating a new deployment without commiting.
        currentuser = cherrypy.serving.request.currentuser
        deployment = environment.create_deployment(owner=currentuser)
        # Store the last change ID as a reference
        form = DeployForm()
        form.last_change.default = deployment.end_id
        if not form.is_submitted():
            # Expect POST
            raise cherrypy.HTTPError(405)
        if form.validate():
            deployment.add().commit()
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
        # Find environment or return Not Found
        environment = self._get_or_404(key)
        # List all activities by dates
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
                for obj in environment.pending_changes
            ]
        }


EnvironmentPage._cp_dispatch = cherrypy.popargs('key', handler=EnvironmentPage())


class EnvironmentApi(CommonApi):
    def __init__(self):
        super().__init__(
            Environment,
            list_perm=User.PERM_NETWORK_LIST,
            edit_perm=User.PERM_ENVIRONMENT_EDIT,
            new_perm=User.PERM_ENVIRONMENT_EDIT,
        )
