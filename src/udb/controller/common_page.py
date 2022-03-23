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
from functools import cached_property

import cherrypy
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.inspection import inspect
from wtforms.fields.simple import TextAreaField
from wtforms.validators import InputRequired

from udb.controller import flash, url_for
from udb.core.model import Message, User
from udb.tools.i18n import gettext as _

from .form import CherryForm

logger = logging.getLogger(__name__)


class MessageForm(CherryForm):
    body = TextAreaField(_('Message'), validators=[InputRequired()], render_kw={"placeholder": _("Add a comments")})


@cherrypy.popargs('key')
class CommonPage(object):
    def __init__(
        self, model, object_form: CherryForm, has_new: bool = True, list_role=User.ROLE_GUEST, edit_role=User.ROLE_USER
    ) -> None:
        assert model
        assert object_form
        self.model = model
        self.object_form = object_form
        self.list_role = list_role
        self.edit_role = edit_role
        # Support a primary key based on sqlalquemy
        self.primary_key = inspect(self.model).primary_key[0].name
        # Detect features supported by model.
        self.has_new = has_new
        self.has_status = hasattr(self.model, 'status')
        self.has_owner = hasattr(self.model, 'owner')
        self.has_followers = hasattr(self.model, 'get_followers')
        self.has_messages = hasattr(self.model, 'get_messages')

    def _get_or_404(self, key):
        """
        Get object with the given key or raise a 404 error.
        """
        obj = self.model.query.filter_by(**{self.primary_key: key}).first()
        if not obj:
            raise cherrypy.HTTPError(404)
        return obj

    def _handle_exception(self, e, form=None):
        self.model.session.rollback()
        if isinstance(e, ValueError):
            # For value error, repport the invalidvalue either as flash message or form error.
            if form and len(e.args) == 2 and getattr(form, e.args[0], None):
                getattr(form, e.args[0]).errors.append(e.args[1])
            else:
                flash(_('Invalid value: %s') % e, level='error')
        elif isinstance(e, IntegrityError) and 'UNIQUE' in str(e):
            # For database integrity error, try to identify the field in form. Or repport error as flash.
            msg = _('A record already exists in database with the same value.')
            field = str(e.orig).split('.')[-1]
            if form and getattr(form, field, None):
                getattr(form, field).errors.append(msg)
            else:
                flash(msg, level='error')
        else:
            flash(_('Database error: %s') % e, level='error')
            logger.warning('database error', exc_info=1)

    def _verify_role(self, role):
        """
        Verify if the current user has the required role.
        """
        user = cherrypy.serving.request.currentuser
        if user is None or not user.has_role(role):
            raise cherrypy.HTTPError(403, 'Insufficient privileges')

    def _verify_sort(self, sort):
        """
        Sort should be formated as follow: <fieldname>_[asc|desc]
        """
        assert sort
        try:
            if sort.endswith('_asc') and hasattr(self.model, sort[0:-4]):
                return getattr(self.model, sort[0:-4]).asc()
            elif sort.endswith('_desc') and hasattr(self.model, sort[0:-5]):
                return getattr(self.model, sort[0:-5]).desc()
        except (AttributeError, NotImplementedError):
            pass
        raise cherrypy.HTTPError(404, 'invalid sort value:' + sort)

    def _query(self, deleted, personal, sort):
        """
        Build a query with supported feature of the current object class.
        """
        query = self.model.query
        if not deleted and hasattr(self.model, 'status'):
            query = query.filter(self.model.status != self.model.STATUS_DELETED)
        if personal and hasattr(self.model, 'owner'):
            query = query.filter(self.model.owner == cherrypy.request.currentuser)
        if sort:
            query = query.order_by(self._verify_sort(sort))
        return query

    @cached_property
    def _sortable_fields(self):
        """
        Return list of sortables fields for the current model.
        """
        fields = []
        for field in self.object_form():
            try:
                getattr(self.model, field.name).asc()
                fields.append(field.name)
            except (AttributeError, NotImplementedError):
                pass
        return fields

    def _key(self, obj):
        """
        Return a string representation of this object primary key.
        """
        return getattr(obj, self.primary_key)

    @cherrypy.expose
    @cherrypy.tools.jinja2(template=['{model_name}/list.html', 'common/list.html'])
    def index(self, deleted=False, personal=False, sort=None, filter=None):
        self._verify_role(self.list_role)
        # Convert from string to boolean
        with cherrypy.HTTPError.handle(ValueError, 400):
            deleted = deleted in [True, 'True', 'true']
            personal = personal in [True, 'True', 'true']
        # Build query
        obj_list = self._query(deleted, personal, sort)
        # return data for templates
        return {
            'has_new': self.has_new,
            'has_status': self.has_status,
            'has_owner': self.has_owner,
            'has_followers': self.has_followers,
            'has_messages': self.has_messages,
            'sortable_fields': self._sortable_fields,
            # TODO Rename those attributes to filter_status
            'deleted': deleted,
            # TODO filter_owner
            'personal': personal,
            'sort': sort,
            'form': self.object_form(),
            'model': self.model,
            'model_name': self.model.__name__.lower(),
            'obj_list': obj_list,
            'display_name': self.object_form.get_display_name(),
        }

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
            except Exception as e:
                self.model.session.rollback()
                self._handle_exception(e, form)
            else:
                raise cherrypy.HTTPRedirect(url_for(self.model))
        # return data form template
        return {
            'model': self.model,
            'model_name': self.model.__name__.lower(),
            'form': form,
            'display_name': self.object_form.get_display_name(),
        }

    @cherrypy.expose
    def status(self, status, key, **kwargs):
        """
        Soft-delete the record.
        """
        self._verify_role(self.edit_role)
        obj = self._get_or_404(key)
        try:
            obj.status = status
            obj.add()
        except Exception as e:
            self.model.session.rollback()
            self._handle_exception(e)
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
            except Exception as e:
                self.model.session.rollback()
                self._handle_exception(e)
            else:
                raise cherrypy.HTTPRedirect(url_for(self.model))
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
            'display_name': self.object_form.get_display_name(),
        }

    @cherrypy.expose
    def follow(self, user_id, key, **kwargs):
        """
        Add current user to the list of followers.
        """
        self._verify_role(self.list_role)
        obj = self._get_or_404(key)
        userobj = User.query.filter_by(id=user_id).first()
        if userobj and not obj.is_following(userobj):
            obj.add_follower(userobj)
            obj.add()
        raise cherrypy.HTTPRedirect(url_for(obj, 'edit'))

    @cherrypy.expose
    def unfollow(self, user_id, key, **kwargs):
        """
        Add current user to the list of followers.
        """
        self._verify_role(self.list_role)
        obj = self._get_or_404(key)
        userobj = User.query.filter_by(id=user_id).first()
        if userobj and obj.is_following(userobj):
            obj.remove_follower(userobj)
            obj.add()
        raise cherrypy.HTTPRedirect(url_for(obj, 'edit'))

    @cherrypy.expose
    def post(self, key, **kwargs):
        self._verify_role(self.list_role)
        obj = self._get_or_404(key)
        form = MessageForm()
        if form.validate_on_submit():
            message = Message(body=form.body.data, author=cherrypy.request.currentuser)
            obj.add_message(message)
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
        obj.session.commit()
        return self._get_or_404(id).to_json()
