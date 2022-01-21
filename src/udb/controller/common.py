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
import cherrypy
from udb.controller import flash, url_for
from udb.core.model import Message, User
from udb.tools.i18n import gettext as _
from wtforms.fields.simple import TextAreaField
from wtforms.validators import InputRequired

from .wtf import CherryForm


class MessageForm(CherryForm):
    body = TextAreaField(
        _('Message'),
        validators=[InputRequired()],
        render_kw={"placeholder": _("Add a comments")})


@cherrypy.popargs('id')
class CommonPage(object):

    def __init__(self, base_url: str, object_cls, object_form: CherryForm) -> None:
        assert base_url
        assert object_cls
        assert object_form
        self.base_url = base_url
        self.object_cls = object_cls
        self.object_form = object_form

    def _get_or_404(self, id):
        """
        Get object with the given id or raise a 404 error.
        """
        obj = self.object_cls.query.filter_by(id=id).first()
        if not obj:
            raise cherrypy.HTTPError(404)
        return obj

    @cherrypy.expose
    @cherrypy.tools.jinja2(template='common-list.html')
    def index(self, deleted=False, personal=False):
        # Convert from string to boolean
        with cherrypy.HTTPError.handle(ValueError, 400):
            deleted = deleted in [True, 'True', 'true']
            personal = personal in [True, 'True', 'true']
        # Build query
        query = self.object_cls.query
        if not deleted:
            query = query.filter(self.object_cls.status
                                 != self.object_cls.STATUS_DELETED)
        if personal:
            query = query.filter(self.object_cls.owner
                                 == cherrypy.request.currentuser)
        obj_list = query.all()
        return {
            'deleted': deleted,
            'personal': personal,
            'form': self.object_form(),
            'base_url': self.base_url,
            'obj_list': obj_list,
            'display_name': self.object_form.get_display_name(),
        }

    @cherrypy.expose
    @cherrypy.tools.jinja2(template='common-new.html')
    def new(self, **kwargs):
        form = self.object_form()
        if form.validate_on_submit():
            obj = self.object_cls()
            try:
                form.populate_obj(obj)
            except ValueError as e:
                if len(e.args) == 2 and getattr(form, e.args[0]):
                    getattr(form, e.args[0]).errors.append(e.args[1])
                else:
                    flash(_('Invalid value: %s') % e, level='error')
            else:
                obj.add()
                raise cherrypy.HTTPRedirect(url_for(self.base_url))
        return {
            'base_url': self.base_url,
            'form': form,
            'display_name': self.object_form.get_display_name(),
        }

    @cherrypy.expose
    def status(self, status, id, **kwargs):
        """
        Soft-delete the record.
        """
        obj = self._get_or_404(id)
        try:
            obj.status = status
            obj.add()
        except ValueError as e:
            # raised by SQLAlchemy validators
            flash(_('Invalid status: %s') % e, level='error')
        raise cherrypy.HTTPRedirect(url_for(self.base_url, id, 'edit'))

    @cherrypy.expose
    @cherrypy.tools.jinja2(template='common-edit.html')
    def edit(self, id, **kwargs):
        # Return Not found if object doesn't exists
        obj = self._get_or_404(id)
        # Update object if form was submited
        form = self.object_form(obj=obj)
        if form.validate_on_submit():
            try:
                form.populate_obj(obj)
            except ValueError as e:
                # raised by SQLAlchemy validators
                if len(e.args) == 2 and getattr(form, e.args[0]):
                    getattr(form, e.args[0]).errors.append(e.args[1])
                else:
                    flash(_('Invalid value: %s') % e, level='error')
            else:
                obj.add()
                raise cherrypy.HTTPRedirect(url_for(self.base_url))
        # Return object form
        return {
            'base_url': self.base_url,
            'form': form,
            'message_form': MessageForm(),
            'obj': obj,
            'display_name': self.object_form.get_display_name(),
        }

    @cherrypy.expose
    def follow(self, user_id, id, **kwargs):
        """
        Add current user to the list of followers.
        """
        obj = self._get_or_404(id)
        userobj = User.query.filter_by(id=user_id).first()
        if userobj and not obj.is_following(userobj):
            obj.add_follower(userobj)
            obj.add()
        raise cherrypy.HTTPRedirect(url_for(self.base_url, obj.id, 'edit'))

    @cherrypy.expose
    def unfollow(self, user_id, id, **kwargs):
        """
        Add current user to the list of followers.
        """
        obj = self._get_or_404(id)
        userobj = User.query.filter_by(id=user_id).first()
        if userobj and obj.is_following(userobj):
            obj.remove_follower(userobj)
            obj.add()
        raise cherrypy.HTTPRedirect(url_for(self.base_url, obj.id, 'edit'))

    @cherrypy.expose
    def post(self, id, **kwargs):
        obj = self._get_or_404(id)
        form = MessageForm()
        if form.validate_on_submit():
            message = Message(
                body=form.body.data,
                author=cherrypy.request.currentuser)
            obj.add_message(message)
        raise cherrypy.HTTPRedirect(url_for(self.base_url, obj.id, 'edit'))


class CommonApi(object):

    def __init__(self, object_cls):
        assert object_cls
        self.object_cls = object_cls

    @cherrypy.expose()
    def default(self, id=None, **kwargs):
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

    def list(self, **kwargs):
        return [obj.to_json() for obj in self.object_cls.query.all()]

    def get(self, id, **kwargs):
        return self._get_or_404(id).to_json()

    def put(self, id, **kwargs):
        """
        Update an existing record.
        """
        data = cherrypy.request.json
        obj = self._get_or_404(id)
        try:
            obj.from_json(data)
            obj.add()
            self.object_cls.session.commit()
        except ValueError as e:
            # raised by SQLAlchemy validators
            raise cherrypy.HTTPError(400, _('Invalid value: %s') % e)
        return self._get_or_404(obj.id).to_json()

    def post(self, **kwargs):
        """
        Create a new record
        """
        data = cherrypy.request.json
        obj = self.object_cls()
        try:
            obj.from_json(data)
            obj.add()
            self.object_cls.session.commit()
        except ValueError as e:
            # raised by SQLAlchemy validators
            raise cherrypy.HTTPError(400, _('Invalid value: %s') % e)
        return self._get_or_404(obj.id).to_json()

    def delete(self, id, **kwargs):
        obj = self._get_or_404(id)
        obj.status = self.object_cls.STATUS_DELETED
        obj.add()
        obj.session.commit()
        return self._get_or_404(id).to_json()
