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
from collections import namedtuple

import cherrypy
from sqlalchemy.exc import DatabaseError
from sqlalchemy.inspection import inspect
from wtforms.fields import TextAreaField
from wtforms.validators import InputRequired, Length

from udb.controller import flash, show_exception, url_for, verify_perm
from udb.core.model import Message, Rule, RuleError, User
from udb.tools.i18n import gettext_lazy as _

from .form import CherryForm

logger = logging.getLogger(__name__)


HistoryRow = namedtuple('HistoryRow', ['id', 'author', 'date', 'type', 'body', 'changes'])


class MessageForm(CherryForm):
    body = TextAreaField(
        _('Message'),
        validators=[
            InputRequired(),
            Length(max=65024),
        ],
        render_kw={"placeholder": _("Add a comments")},
    )


@cherrypy.popargs('key')
class CommonPage(object):
    def __init__(
        self,
        model,
        edit_form: CherryForm,
        new_form: CherryForm = None,
        has_new: bool = True,
        list_perm=User.PERM_NETWORK_LIST,
        edit_perm=User.PERM_NETWORK_EDIT,
        new_perm=User.PERM_NETWORK_EDIT,
    ) -> None:
        assert model
        assert edit_form
        self.model = model
        self.edit_form = edit_form
        self.new_form = new_form if new_form else edit_form
        self.list_perm = list_perm
        self.edit_perm = edit_perm
        self.new_perm = new_perm
        # Support a primary key based on sqlalquemy
        self.primary_key = inspect(self.model).primary_key[0].name
        # Detect features supported by model.
        self.has_new = has_new
        self.has_status = hasattr(self.model, 'status')
        self.has_followers = hasattr(self.model, 'followers')
        self.has_messages = hasattr(self.model, 'messages')

    def _get_or_404(self, key):
        """
        Get object with the given key or raise a 404 error.
        """
        obj = self._get_query(key).first()
        if not obj:
            raise cherrypy.HTTPError(404)
        return obj

    def _list_query(self):
        """
        Build a query with supported feature of the current object class.
        """
        raise NotImplementedError('subclass must implement this function')

    def _get_query(self, key):
        """
        Build a query with supported feature of the current object class.
        """
        return self.model.query.filter_by(**{self.primary_key: key})

    def _to_list(self, data):
        if not isinstance(data, list):
            data = list(data)
        data.append(url_for(self.model, data[0], 'edit', relative='server'))
        return data

    @cherrypy.expose
    @cherrypy.tools.jinja2(template=['{model_name}/list.html', 'common/list.html'])
    def index(self):
        verify_perm(self.list_perm)
        currentuser = cherrypy.serving.request.currentuser
        # return data for templates
        return {
            'has_new': self.has_new,
            'new_perm': self.has_new and currentuser.has_permissions(self.new_perm),
            'form': self.edit_form(),
            'model': self.model,
            'model_name': self.model.__name__.lower(),
        }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def data_json(self, **kwargs):
        verify_perm(self.list_perm)
        obj_list = self._list_query()
        data = {'data': [self._to_list(obj) for obj in obj_list]}
        return data

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def messages(self, key, **kwargs):
        verify_perm(self.list_perm)
        # Return Not found if object doesn't exists
        obj = self._get_or_404(key)
        # Query Object Messages
        query = (
            Message.query.with_entities(
                Message.id,
                User.summary.label('author_name'),
                Message.date,
                Message.type,
                Message.body,
                Message._changes.label('changes'),
            )
            .outerjoin(Message.author)
            .order_by(Message.date.desc())
            .filter(Message.model_id == obj.id, Message.model_name == obj.__tablename__)
        )
        data = query.all()
        return {
            'data': [
                HistoryRow(
                    id=obj.id,
                    author=obj.author_name or str(_('System')),
                    date=obj.date.isoformat(),
                    type=obj.type,
                    body=obj.body,
                    changes=Message.json_changes(obj.changes),
                )
                for obj in data
            ]
        }

    @cherrypy.expose
    @cherrypy.tools.jinja2(template=['{model_name}/new.html', 'common/new.html'])
    def new(self, **kwargs):
        verify_perm(self.new_perm)
        # Validate form
        form = self.new_form()
        if form.validate_on_submit():
            obj = self.model()
            try:
                form.populate_obj(obj)
                obj.add().flush()
                # Check enforced rules
                Rule.verify(obj, errors='raise', severity=Rule.SEVERITY_ENFORCED)
                obj.commit()
            except Exception as e:
                cherrypy.tools.db.get_session().rollback()
                show_exception(e, form=form, obj=obj)
            else:
                flash(_('Record created successfully.'))
                # Redirect user to same record
                Rule.verify(obj)
                raise cherrypy.HTTPRedirect(url_for(obj, 'edit'))
        elif not form.is_submitted():
            # Apply the default value from params
            # Every query string starting with "d-" are used to define default value to pre-populate the fields.
            for key, value in kwargs.items():
                if key.startswith('d-') and hasattr(form, key[2:]):
                    getattr(form, key[2:]).default = value
            form.process()
        # return data form template
        return {
            'model': self.model,
            'model_name': self.model.__name__.lower(),
            'form': form,
        }

    @cherrypy.expose
    @cherrypy.tools.jinja2(template=['{model_name}/edit.html', 'common/edit.html'])
    def edit(self, key, **kwargs):
        currentuser = cherrypy.serving.request.currentuser
        verify_perm(self.list_perm)
        # Return Not found if object doesn't exists
        obj = self._get_or_404(key)
        # Update object if form was submited
        form = self.edit_form(obj=obj)
        if form.validate_on_submit():
            verify_perm(self.edit_perm)
            try:
                obj_copy = dict(obj.__dict__)
                form.populate_obj(obj)
                obj_copy = dict(obj.__dict__)
                # Add Message to explain changes.
                body = kwargs.get('body', False)
                if self.has_messages and body:
                    message = Message(body=body, author=currentuser)
                    obj.add_message(message)
                # Update status
                status = kwargs.get('status', None)
                if self.has_status and status:
                    obj.status = int(status)
                obj.add().flush()
                # Check enforced rules and raise error if required to prevent record from being saved.
                Rule.verify(obj, errors='raise', severity=Rule.SEVERITY_ENFORCED)
                obj.commit()
            except Exception as e:
                cherrypy.tools.db.get_session().rollback()
                # Recreate an object from the copied fields to make sure the message contains the right values.
                obj_copy.pop('_sa_instance_state')
                edited_obj = self.model(**obj_copy)
                show_exception(e, form=form, obj=edited_obj)
                # Then we need to rollback to clear the sqlalchemy session.
                cherrypy.tools.db.get_session().rollback()
            else:
                flash(_('Record updated successfully'))
                Rule.verify(obj)
                raise cherrypy.HTTPRedirect(url_for(obj, 'edit'))
        else:
            # Run Soft Rules
            for row in Rule.verify(obj):
                show_exception(RuleError(row), form=form, obj=obj)

        # Return object form
        return {
            'has_status': self.has_status,
            'has_followers': self.has_followers,
            'has_messages': self.has_messages,
            'edit_perm': currentuser.has_permissions(self.edit_perm),
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
        verify_perm(self.list_perm)
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
        verify_perm(self.list_perm)
        obj = self._get_or_404(key)
        userobj = User.query.filter_by(id=user_id).first()
        if userobj and obj.is_following(userobj):
            obj.remove_follower(userobj)
            obj.commit()
        raise cherrypy.HTTPRedirect(url_for(obj, 'edit'))


@cherrypy.expose
@cherrypy.tools.errors(
    error_table={
        ValueError: 400,
        DatabaseError: 400,
    }
)
class CommonApi(object):
    def __init__(
        self,
        object_cls,
        list_perm=User.PERM_NETWORK_LIST,
        edit_perm=User.PERM_NETWORK_EDIT,
        new_perm=User.PERM_NETWORK_EDIT,
    ):
        assert object_cls
        self.object_cls = object_cls
        self.list_perm = list_perm
        self.edit_perm = edit_perm
        self.new_perm = new_perm

    def _get_or_404(self, id):
        """
        Get object with the given id or raise a 404 error.
        """
        obj = self.object_cls.query.filter_by(id=id).first()
        if not obj:
            raise cherrypy.HTTPError(404, "Record ID not found")
        return obj

    def list(self, **kwargs):
        return [obj.to_json() for obj in self.object_cls.query.all()]

    def get(self, id, **kwargs):
        return self._get_or_404(id).to_json()

    def put(self, id, **kwargs):
        """
        Update an existing record.
        """
        verify_perm(self.edit_perm)
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
        verify_perm(self.new_perm)
        data = cherrypy.request.json
        obj = self.object_cls()
        obj.from_json(data)
        obj.add()
        self.object_cls.session.commit()
        return self._get_or_404(obj.id).to_json()

    def delete(self, id, **kwargs):
        verify_perm(self.edit_perm)
        obj = self._get_or_404(id)
        obj.status = self.object_cls.STATUS_DELETED
        obj.add()
        obj.commit()
        return self._get_or_404(id).to_json()
