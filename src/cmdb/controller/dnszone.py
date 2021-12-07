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
from cmdb.controller import url_for
from cmdb.core.model import DnsZone, Message, User
from cmdb.tools.i18n import gettext as _
from wtforms.fields import StringField
from wtforms.fields.core import DateTimeField
from wtforms.fields.simple import TextAreaField
from wtforms.validators import InputRequired

from .fields import UserField
from .wtf import CherryForm


class DnsZoneCreateForm(CherryForm):
    name = StringField(
        _('Name'),
        validators=[InputRequired()],
        render_kw={"placeholder": _("Enter a FQDN")})
    notes = TextAreaField(
        _('Notes'),
        default='',
        validators=[],
        render_kw={"placeholder": _("Enter details information about this DNS Zone")})
    owner_id = UserField(
        _('Owner'),
        default=lambda: cherrypy.serving.request.currentuser.id)


class DnsZoneEditForm(DnsZoneCreateForm):
    created_at = DateTimeField(
        _('Date de création'),
        render_kw={'readonly': True})
    modified_at = DateTimeField(
        _('Dernière mise à jours'),
        render_kw={'readonly': True})


class MessageForm(CherryForm):
    body = TextAreaField(
        _('Message'),
        validators=[InputRequired()],
        render_kw={"placeholder": _("Add a comments")})


@cherrypy.popargs('id')
class DnsZonePage():

    def _get_or_404(self, id):
        dnszone = DnsZone.query.filter_by(id=id).first()
        if not dnszone:
            raise cherrypy.HTTPError(404)
        return dnszone

    @cherrypy.expose
    @cherrypy.tools.jinja2(template='dnszone.html')
    def index(self):
        return {'dnszone_list': DnsZone.query.all()}

    @cherrypy.expose
    @cherrypy.tools.jinja2(template='dnszone-new.html')
    def new(self, **kwargs):
        form = DnsZoneCreateForm()
        if form.validate_on_submit():
            dnszone = DnsZone()
            form.populate_obj(dnszone)
            DnsZone.session.add(dnszone)
            # redirect to index
            raise cherrypy.HTTPRedirect(url_for('dnszone'))
        return {'form': form}

    @cherrypy.expose
    @cherrypy.tools.jinja2(template='dnszone-edit.html')
    def edit(self, id, **kwargs):
        # Return Not found if object doesn't exists
        dnszone = self._get_or_404(id)
        # Update object if form was submited
        form = DnsZoneEditForm(obj=dnszone)
        if form.validate_on_submit():
            form.populate_obj(dnszone)
            DnsZone.session.add(dnszone)
            # redirect to index
            raise cherrypy.HTTPRedirect(url_for('dnszone'))
        # Return object form
        return {'form': form, 'message_form': MessageForm(), 'dnszone': dnszone}

    @cherrypy.expose
    def follow(self, user_id=None, **kwargs):
        """
        Add current user to the list of followers.
        """
        dnszone = self._get_or_404(kwargs.get('id', None))
        if user_id is None:
            userobj = cherrypy.request.currentuser
        else:
            userobj = User.query.filter_by(id=1).first()
        if userobj and not dnszone.is_following(userobj):
            dnszone.followers.append(userobj)
            DnsZone.session.add(dnszone)
        raise cherrypy.HTTPRedirect(url_for('dnszone', dnszone.id, 'edit'))

    @cherrypy.expose
    def unfollow(self, user_id=None, **kwargs):
        """
        Add current user to the list of followers.
        """
        dnszone = self._get_or_404(kwargs.get('id', None))
        if user_id is None:
            userobj = cherrypy.request.currentuser
        else:
            userobj = User.query.filter_by(id=1).first()
        if userobj and dnszone.is_following(userobj):
            dnszone.followers.remove(userobj)
            DnsZone.session.add(dnszone)
        raise cherrypy.HTTPRedirect(url_for('dnszone', dnszone.id, 'edit'))

    @cherrypy.expose
    def post(self, id, **kwargs):
        dnszone = self._get_or_404(id)
        form = MessageForm()
        if form.validate_on_submit():
            message = Message(
                body=form.body.data,
                author=cherrypy.request.currentuser).add()
            dnszone.messages.append(message)
            dnszone.add()

        raise cherrypy.HTTPRedirect(url_for('dnszone', dnszone.id, 'edit'))
