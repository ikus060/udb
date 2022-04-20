# -*- coding: utf-8 -*-
# udb, A web interface to manage IT network
# Copyright (C) 2022 IKUS Software
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
from cherrypy.process.plugins import SimplePlugin
from sqlalchemy.event import listen, remove

from udb.core.model import Message
from udb.tools.i18n import gettext_lazy as _

Session = cherrypy.tools.db.get_session()


class NotifiationPlugin(SimplePlugin):
    env = None
    header_name = ''
    catch_all_email = None

    def start(self):
        self.bus.log('Start Notification plugins')
        # Register a listener with sqlalquemy
        listen(Session, "after_flush", self._after_flush)

    def stop(self):
        self.bus.log('Stop Notification plugins')
        remove(Session, "after_flush", self._after_flush)

    def _after_flush(self, session, flush_context):
        """
        Send email notification on object changes.
        """
        messages = [msg for msg in session.new if isinstance(msg, Message)]
        if not messages:
            return
        # Collect list of model
        obj_list = sorted([msg.model_object for msg in messages], key=lambda obj: (obj.display_name, obj.id))
        if not obj_list:
            return
        # Send email to each follower except the author
        bcc = list(
            {user.email for obj in obj_list for user in obj.followers if messages[0].author_id != user.id if user.email}
        )
        # Send email to catch-all notification email.
        if self.catch_all_email:
            bcc += [self.catch_all_email]
        if not bcc:
            return

        # Get jinja2 template to generate email body
        template = self.env.get_template('mail/notification.html')
        values = {
            'header_name': self.header_name,
            'messages': messages,
        }
        if len(messages) > 1:
            subject = _('%s modified by %s') % (
                ', '.join([obj.summary for obj in obj_list]),
                messages[0].author_name,
            )
        elif messages[0].type == Message.TYPE_COMMENT:
            subject = _('Comment on %s %s by %s') % (
                messages[0].model_object.display_name,
                messages[0].model_object.summary,
                messages[0].author_name,
            )
        else:
            subject = _('%s %s modified by %s') % (
                messages[0].model_object.display_name,
                messages[0].model_object.summary,
                messages[0].author_name,
            )
        message_body = template.render(**values)

        if bcc:
            self.bus.publish('queue_mail', bcc=bcc, subject=subject, message=message_body)


cherrypy.notification = NotifiationPlugin(cherrypy.engine)
cherrypy.notification.subscribe()

cherrypy.config.namespaces['notification'] = lambda key, value: setattr(cherrypy.notification, key, value)
