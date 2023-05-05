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
from sqlalchemy import and_, literal, select, union_all
from wtforms.fields import BooleanField

from udb.controller import flash, handle_exception, url_for
from udb.core.model import Follower, followable_model_name, followable_models
from udb.tools.i18n import gettext_lazy as _

from .form import CherryForm

AllModel = union_all(
    *[
        select(
            literal(model.__name__.lower()).label('model_name'),
            model.id.label('model_id'),
            getattr(model, 'status', literal('enabled')).label('status'),
            model.summary,
        )
        for model in followable_models
    ]
).alias()


class NotificationFormBase(CherryForm):
    """
    Form to modify subscribe to "all".
    """

    def __init__(self, obj, **kwargs):
        # Pass initial data to the form using the follower(s)
        model_names = self._get_current_value(obj)
        data = {model_name: True for model_name in model_names}
        super().__init__(data=data, **kwargs)

    def _get_current_value(self, obj):
        # Get list of follow "all" (where model_id == 0)
        rows = (
            Follower.session.query(Follower.model_name).filter(Follower.user_id == obj.id, Follower.model_id == 0).all()
        )
        return [r[0] for r in rows]

    def populate_obj(self, obj):
        # Query current state
        model_names = self._get_current_value(obj)
        # Add or remove Followers
        for field in self:
            model_name = field.name
            if field.data:
                # Add new follower where requested
                if model_name not in model_names:
                    Follower(user_id=obj.id, model_id=0, model_name=model_name).add()
            else:
                # Remove follower where not requested
                if model_name in model_names:
                    Follower.query.filter(
                        Follower.user_id == obj.id, Follower.model_id == 0, Follower.model_name == model_name
                    ).delete()


def create_notification_form(obj):
    """
    Form builder to dynamically create form with model_name fields.
    """
    assert obj, 'user object is required'

    class Form(NotificationFormBase):
        pass

    # Dynamically, create a list of model that could be followed.
    for model_name in followable_model_name:
        setattr(Form, model_name, BooleanField(label=model_name))

    return Form(obj)


class NotificationsPage:
    @cherrypy.expose()
    @cherrypy.tools.jinja2(template=['notifications.html'])
    def index(self, **kwargs):
        obj = cherrypy.request.currentuser
        form = create_notification_form(obj=obj)
        if form.validate_on_submit():
            try:
                form.populate_obj(obj=obj)
                obj.add()
                obj.commit()
            except Exception as e:
                handle_exception(e, form)
            else:
                flash(_('Notification settings updated successfully.'))
                raise cherrypy.HTTPRedirect(url_for('notifications', ''))
        return {
            'form': form,
        }

    @cherrypy.expose()
    def unfollow(self, **kwargs):
        """
        Called to unfollow all record.
        """
        # Validate Method
        if cherrypy.request.method not in ['POST', 'PUT']:
            raise cherrypy.HTTPError(405)
        # Remove all follow for current user
        userobj = cherrypy.request.currentuser
        Follower.query.filter(Follower.user_id == userobj.id, Follower.model_id != 0).delete()
        Follower.session.commit()
        raise cherrypy.HTTPRedirect(url_for('notifications', ''))

    @cherrypy.expose()
    @cherrypy.tools.json_out()
    def data_json(self, **kwargs):
        # List object followed by current user
        userobj = cherrypy.request.currentuser
        query = (
            Follower.session.query(
                Follower.model_id,
                AllModel.c.status,
                Follower.model_name,
                AllModel.c.summary,
            )
            .join(
                AllModel,
                and_(
                    Follower.model_name == AllModel.c.model_name,
                    Follower.model_id == AllModel.c.model_id,
                    Follower.model_id != 0,
                ),
            )
            .filter(Follower.user_id == userobj.id)
        )
        return {
            'data': [
                [
                    obj.model_id,
                    obj.status,
                    obj.model_name,
                    obj.summary,
                    url_for(obj, 'edit'),
                ]
                for obj in query.all()
            ]
        }
