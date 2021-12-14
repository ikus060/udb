# -*- coding: utf-8 -*-
# cmdb, A web interface to manage IT network CMDB
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
from cmdb.controller import flash, url_for
from cmdb.core.model import Message, User
from cmdb.tools.i18n import gettext as _
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
    def index(self):
        return {
            'form': self.object_form(),
            'base_url': self.base_url,
            'obj_list': self.object_cls.query.all(),
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
                # raised by SQLAlchemy validators
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
    def follow(self, user_id=None, **kwargs):
        """
        Add current user to the list of followers.
        """
        obj = self._get_or_404(kwargs.get('id', None))
        if user_id is None:
            userobj = cherrypy.request.currentuser
        else:
            userobj = User.query.filter_by(id=1).first()
        if userobj and not obj.is_following(userobj):
            obj.followers.append(userobj)
            obj.add()
        raise cherrypy.HTTPRedirect(url_for(self.base_url, obj.id, 'edit'))

    @cherrypy.expose
    def unfollow(self, user_id=None, **kwargs):
        """
        Add current user to the list of followers.
        """
        obj = self._get_or_404(kwargs.get('id', None))
        if user_id is None:
            userobj = cherrypy.request.currentuser
        else:
            userobj = User.query.filter_by(id=1).first()
        if userobj and obj.is_following(userobj):
            obj.followers.remove(userobj)
            obj.add()
        raise cherrypy.HTTPRedirect(url_for(self.base_url, obj.id, 'edit'))

    @cherrypy.expose
    def post(self, id, **kwargs):
        obj = self._get_or_404(id)
        form = MessageForm()
        if form.validate_on_submit():
            message = Message(
                body=form.body.data,
                author=cherrypy.request.currentuser).add()
            obj.messages.append(message)
            obj.add()
        raise cherrypy.HTTPRedirect(url_for(self.base_url, obj.id, 'edit'))
