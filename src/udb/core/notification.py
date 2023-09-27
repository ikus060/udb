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

import re
import threading
from collections import namedtuple

import cherrypy
from cherrypy.process.plugins import SimplePlugin
from sqlalchemy import and_, or_
from sqlalchemy.event import listen, remove

from udb.core.model import Follower, Message, User
from udb.tools.i18n import gettext_lazy as _
from udb.tools.i18n import preferred_lang, preferred_timezone

Session = cherrypy.tools.db.get_session()

Recipient = namedtuple('Recipient', 'email,lang,timezone')


class NotifiationPlugin(SimplePlugin):
    env = None
    header_name = ''
    catch_all_email = None

    _lock = threading.RLock()

    def start(self):
        self.bus.log('Start Notification plugins')
        self._new_messages = {}
        # Register a listener with sqlalquemy
        listen(Session, "after_flush", self._after_flush)
        listen(Session, "after_commit", self._after_commit)

    def stop(self):
        self.bus.log('Stop Notification plugins')
        remove(Session, "after_flush", self._after_flush)
        remove(Session, "after_commit", self._after_commit)
        self._new_messages = {}

    def _after_flush(self, session, flush_context):
        """
        Check if this database session created new message objects.
        """
        # Get list of new messages
        new_messages = [msg for msg in session.new if isinstance(msg, Message)]
        if not new_messages:
            return
        # Keep track if this session had new messages.
        self._new_messages[session] = bool(new_messages) or self._new_messages.get(session, False)

    def _after_commit(self, session):
        """
        On commit, let check if new message was created and send
        the corresponding notification.
        """
        # Check if this session contain new messages
        if session not in self._new_messages:
            return
        elif not self._new_messages[session]:
            del self._new_messages[session]
            return

        # On every commit, let trigger a background task to collect
        # Messages to be notified.
        del self._new_messages[session]
        self.bus.publish('schedule_task', self._notification_task)

    def _notification_task(self):
        """
        Task to notify users following modification on records.
        """
        # Let use python lock to minimize the lock on database
        with self._lock:
            all_messages = (
                Message.query.filter(Message.sent.is_not(True)).order_by(Message.model_name, Message.model_id).all()
            )
            if not all_messages:
                return

            # For each message determine the recipients
            final_recipients = {}
            for message in all_messages:
                recipients = self._get_recipients(message)
                for recipient in recipients:
                    final_recipients.setdefault(recipient, []).append(message)

            # For each recipients send the messages
            for recipient, messages in final_recipients.items():
                self._send_notification(messages, recipient)

            # Update the "sent" flag
            for message in all_messages:
                message.sent = True
                message.add()
            Message.session.commit()

    def _get_recipients(self, message):

        # Get list of all the followers. Query database for matching model_name and model_id.
        criteria = [
            and_(Follower.model_name == model_name, Follower.model_id == id)
            for model_name, id in message.model_object.objects_to_notify()
        ]
        # Follower with model_id == 0 must receive all changes for the given model.
        criteria.extend(
            [
                and_(
                    Follower.model_id == 0,
                    Follower.model_name.in_(
                        list(set([model_name for model_name, id in message.model_object.objects_to_notify()]))
                    ),
                )
            ]
        )
        criteria = or_(*criteria)
        followers = (
            User.session.query(User.email, User.lang, User.timezone)
            .distinct()
            .join(Follower)
            .filter(criteria)
            .filter(User.email.is_not(None), User.email != '', User.estatus == User.STATUS_ENABLED)
            .all()
        )
        bcc = [Recipient(user.email, user.lang, user.timezone) for user in followers]

        # Changes made to user object should always be send to the user it-self.
        if (
            message.model_name == User.__tablename__
            and any(attr in message.changes for attr in ['status', 'password', 'email', 'role'])
            and message.user_object
            and message.user_object.email
        ):
            user = message.user_object
            bcc += [Recipient(user.email, user.lang, user.timezone)]
            # Also send email to previous email value when email get updated.
            if 'email' in message.changes and message.changes['email'][0]:
                bcc += [Recipient(message.changes['email'][0], user.lang, user.timezone)]

        # Send email to catch-all notification email.
        if self.catch_all_email:
            bcc += [Recipient(self.catch_all_email, None, None)]
        return bcc

    def _send_notification(self, messages, recipient):
        assert recipient
        # Get jinja2 template to generate email body
        template = self.env.get_template('mail/notification.html')
        values = {
            'header_name': self.header_name,
            'messages': messages,
        }
        # Renger message using user lang and timezone
        with preferred_lang(recipient.lang):
            with preferred_timezone(recipient.timezone):
                message_body = template.render(**values)
        # Extract title and use it as subject
        m = re.search(r'<title>(.*)</title>', message_body, re.DOTALL)
        if m:
            subject = m.group(1).replace('\n', '').strip()
        else:
            subject = _('Notification')
        self.bus.publish('send_mail', to=recipient.email, subject=subject, message=message_body)


cherrypy.notification = NotifiationPlugin(cherrypy.engine)
cherrypy.notification.subscribe()

cherrypy.config.namespaces['notification'] = lambda key, value: setattr(cherrypy.notification, key, value)
