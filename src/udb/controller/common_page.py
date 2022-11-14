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
import logging

import cherrypy
from sqlalchemy.exc import DatabaseError
from sqlalchemy.inspection import inspect
from wtforms.fields import HiddenField, TextAreaField
from wtforms.validators import InputRequired, Length

from udb.controller import flash, handle_exception, url_for
from udb.core.model import Message, User
from udb.tools.i18n import gettext as _

from .form import CherryForm

logger = logging.getLogger(__name__)


class MessageForm(CherryForm):
    body = TextAreaField(
        _('Message'),
        validators=[
            InputRequired(),
            Length(max=65024),
        ],
        render_kw={"placeholder": _("Add a comments")},
    )


class RefererField(HiddenField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, default=lambda: cherrypy.request.headers.get('Referer'), **kwargs)

    def process_formdata(self, valuelist):
        """
        Process value received from form data. Validate the URL.
        """
        # Make sure the Referer is our web application.
        if valuelist and valuelist[0].startswith(cherrypy.request.base):
            self.data = valuelist[0]

    def populate_obj(self, obj, name):
        # Do nothing
        pass


@cherrypy.popargs('key')
class CommonPage(object):
    def __init__(
        self, model, object_form: CherryForm, has_new: bool = True, list_role=User.ROLE_GUEST, edit_role=User.ROLE_USER
    ) -> None:
        assert model
        assert object_form
        self.model = model
        self.object_form = object_form
        self.object_form.referer = RefererField()
        self.list_role = list_role
        self.edit_role = edit_role
        # Support a primary key based on sqlalquemy
        self.primary_key = inspect(self.model).primary_key[0].name
        # Detect features supported by model.
        self.has_new = has_new
        self.has_status = hasattr(self.model, 'status')
        self.has_owner = hasattr(self.model, 'owner')
        self.has_followers = hasattr(self.model, 'followers')
        self.has_messages = hasattr(self.model, 'messages')

    def _get_or_404(self, key):
        """
        Get object with the given key or raise a 404 error.
        """
        obj = self.model.query.filter_by(**{self.primary_key: key}).first()
        if not obj:
            raise cherrypy.HTTPError(404)
        return obj

    def _verify_role(self, role):
        """
        Verify if the current user has the required role.
        """
        user = cherrypy.serving.request.currentuser
        if user is None or not user.has_role(role):
            raise cherrypy.HTTPError(403, 'Insufficient privileges')

    def _query(self):
        """
        Build a query with supported feature of the current object class.
        """
        return self.model.query

    def _key(self, obj):
        """
        Return a string representation of this object primary key.
        """
        return getattr(obj, self.primary_key)

    def _to_json(self, obj):
        data = obj.to_json()
        data['url'] = url_for(obj, 'edit')
        if self.has_owner:
            if obj.owner:
                data['owner'] = obj.owner.to_json()
                data['owner']['url'] = url_for(obj.owner, 'edit')
            else:
                data['owner'] = None
        return data

    @cherrypy.expose
    @cherrypy.tools.jinja2(template=['{model_name}/list.html', 'common/list.html'])
    def index(self):
        self._verify_role(self.list_role)
        # return data for templates
        return {
            'has_new': self.has_new,
            'has_status': self.has_status,
            'has_owner': self.has_owner,
            'has_followers': self.has_followers,
            'has_messages': self.has_messages,
            'form': self.object_form(),
            'model': self.model,
            'model_name': self.model.__name__.lower(),
        }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def data_json(self, **kwargs):
        self._verify_role(self.list_role)
        obj_list = self._query()
        return {'data': [self._to_json(obj) for obj in obj_list]}

    @cherrypy.expose
    @cherrypy.tools.jinja2(template=['{model_name}/new.html', 'common/new.html'])
    def new(self, **kwargs):
        self._verify_role(self.edit_role)
        # Validate form
        form = self.object_form()
        if form.validate_on_submit():
            obj = self.model()
            try:
                form.populate_obj(obj)
                obj.add()
                obj.commit()
            except Exception as e:
                handle_exception(e, form)
            else:
                raise cherrypy.HTTPRedirect(form.referer.data or url_for(self.model))
        # return data form template
        return {
            'model': self.model,
            'model_name': self.model.__name__.lower(),
            'form': form,
        }

    @cherrypy.expose
    def status(self, key, status=None, **kwargs):
        """
        Soft-delete the record.
        """
        if cherrypy.request.method not in ['POST', 'PUT']:
            raise cherrypy.HTTPError(405)
        self._verify_role(self.edit_role)
        obj = self._get_or_404(key)
        try:
            obj.status = status
            obj.add()
            obj.commit()
        except Exception as e:
            handle_exception(e)
        raise cherrypy.HTTPRedirect(url_for(obj, 'edit'))

    @cherrypy.expose
    @cherrypy.tools.jinja2(template=['{model_name}/edit.html', 'common/edit.html'])
    def edit(self, key, **kwargs):
        self._verify_role(self.list_role)
        # Return Not found if object doesn't exists
        obj = self._get_or_404(key)
        # Update object if form was submited
        form = self.object_form(obj=obj)
        if form.validate_on_submit():
            self._verify_role(self.edit_role)
            try:
                form.populate_obj(obj)
                obj.add()
                obj.commit()
            except Exception as e:
                handle_exception(e, form)
            else:
                flash(_('Record updated successfully'))
                raise cherrypy.HTTPRedirect(url_for(obj, 'edit'))
        # Return object form
        return {
            'has_new': self.has_new,
            'has_status': self.has_status,
            'has_owner': self.has_owner,
            'has_followers': self.has_followers,
            'has_messages': self.has_messages,
            'model': self.model,
            'model_name': self.model.__name__.lower(),
            'form': form,
            'message_form': MessageForm(),
            'obj': obj,
        }

    @cherrypy.expose
    def follow(self, key, user_id=None, **kwargs):
        """
        Add current user to the list of followers.
        """
        if cherrypy.request.method not in ['POST', 'PUT']:
            raise cherrypy.HTTPError(405)
        self._verify_role(self.list_role)
        obj = self._get_or_404(key)
        userobj = User.query.filter_by(id=user_id).first()
        if userobj and not obj.is_following(userobj):
            obj.add_follower(userobj)
            obj.commit()
        raise cherrypy.HTTPRedirect(url_for(obj, 'edit'))

    @cherrypy.expose
    def unfollow(self, key, user_id=None, **kwargs):
        """
        Add current user to the list of followers.
        """
        if cherrypy.request.method not in ['POST', 'PUT']:
            raise cherrypy.HTTPError(405)
        self._verify_role(self.list_role)
        obj = self._get_or_404(key)
        userobj = User.query.filter_by(id=user_id).first()
        if userobj and obj.is_following(userobj):
            obj.remove_follower(userobj)
            obj.commit()
        # Redirect to referer if defined
        raise cherrypy.HTTPRedirect(url_for(obj, 'edit'))

    @cherrypy.expose
    def post(self, key, **kwargs):
        self._verify_role(self.list_role)
        obj = self._get_or_404(key)
        form = MessageForm()
        if form.validate_on_submit():
            message = Message(body=form.body.data, author=cherrypy.request.currentuser)
            obj.add_message(message)
            obj.commit()
        raise cherrypy.HTTPRedirect(url_for(obj, 'edit'))


@cherrypy.tools.errors(
    error_table={
        ValueError: 400,
        DatabaseError: 400,
    }
)
class CommonApi(object):
    def __init__(self, object_cls, list_role=User.ROLE_GUEST, edit_role=User.ROLE_USER):
        assert object_cls
        self.object_cls = object_cls
        self.list_role = list_role
        self.edit_role = edit_role

    @cherrypy.expose()
    def default(self, id=None, **kwargs):
        self._verify_role(self.list_role)
        with cherrypy.HTTPError.handle(405):
            method = cherrypy.request.method
            assert method in ['GET', 'PUT', 'POST', 'DELETE']
        if method == 'GET' and id is None:
            return self.list(**kwargs)
        elif method == 'GET':
            return self.get(id, **kwargs)
        elif method == 'PUT':
            return self.put(id, **kwargs)
        elif method == 'DELETE':
            return self.delete(id, **kwargs)
        elif method == 'POST':
            return self.post(**kwargs)

    def _get_or_404(self, id):
        """
        Get object with the given id or raise a 404 error.
        """
        obj = self.object_cls.query.filter_by(id=id).first()
        if not obj:
            raise cherrypy.HTTPError(404)
        return obj

    def _verify_role(self, role):
        """
        Verify if the current user has the required role.
        """
        user = cherrypy.serving.request.currentuser
        if user is None or not user.has_role(role):
            raise cherrypy.HTTPError(403, 'Insufficient privileges')

    def list(self, **kwargs):
        return [obj.to_json() for obj in self.object_cls.query.all()]

    def get(self, id, **kwargs):
        return self._get_or_404(id).to_json()

    def put(self, id, **kwargs):
        """
        Update an existing record.
        """
        self._verify_role(self.edit_role)
        data = cherrypy.request.json
        obj = self._get_or_404(id)
        obj.from_json(data)
        obj.add()
        self.object_cls.session.commit()
        return self._get_or_404(obj.id).to_json()

    def post(self, **kwargs):
        """
        Create a new record
        """
        self._verify_role(self.edit_role)
        data = cherrypy.request.json
        obj = self.object_cls()
        obj.from_json(data)
        obj.add()
        self.object_cls.session.commit()
        return self._get_or_404(obj.id).to_json()

    def delete(self, id, **kwargs):
        self._verify_role(self.edit_role)
        obj = self._get_or_404(id)
        obj.status = self.object_cls.STATUS_DELETED
        obj.add()
        obj.commit()
        return self._get_or_404(id).to_json()
