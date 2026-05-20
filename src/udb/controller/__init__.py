# udb, A web interface to manage IT network
# Copyright (C) 2022-2026 IKUS Software inc.
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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import logging
import re

import cherrypy
from cherrypy_foundation.flash import flash
from cherrypy_foundation.tools.i18n import get_translation
from cherrypy_foundation.tools.i18n import gettext as _
from cherrypy_foundation.url import url_for
from markupsafe import Markup
from sqlalchemy.exc import IntegrityError

from udb.core.model import Environment, Rule, RuleError

logger = logging.getLogger(__name__)


def verify_perm(perm):
    """
    Verify if the current user has the required permissions.
    """
    user = cherrypy.serving.request.currentuser
    if user is None or not user.has_permissions(perm):
        raise cherrypy.HTTPError(403, 'Insufficient privileges')


def template_processor():
    request = cherrypy.serving.request
    values = {
        'lang': str(get_translation().locale),
        'current_url': cherrypy.url(path=request.path_info),
    }
    if hasattr(request, 'login'):
        values['username'] = request.login
    if hasattr(request, 'currentuser'):
        values['currentuser'] = request.currentuser
        values['pending_changes'] = Environment.count_pending_changes()
    return values


def show_exception(e, form=None, obj=None):
    if isinstance(e, ValueError):
        # ValueError are raised by SQLalchemy custom validation
        # For value error, repport the invalid value either as flash message or form error.
        if len(e.args) == 2:
            _show_error(description=_('Invalid value: %s') % e.args[1], field=e.args[0], form=form)
        else:
            _show_error(description=_('Invalid value: %s') % e, form=form)
    elif isinstance(e, IntegrityError):
        # Integrity error are raised by Database
        logger.warning('database integrity error', exc_info=1)
        _show_integrity_error(e, form=form, obj=obj)
    elif isinstance(e, RuleError):
        _show_rule_error(e, form=form, obj=obj)
    else:
        logger.warning('database error', exc_info=1)
        _show_error(description=_('Database error: %s') % e, form=form)


def _show_integrity_error(e, form=None, obj=None):
    """
    This implementation lookup the metadata to find the corresponding
    constraints and retrieve additional information to better help the end-user.
    """
    error = str(e.orig)

    # For Unique constrain violation, we try to identify the field causing the problem to properly
    # attach the error to the fields. If the fields cannot be found using the constrain
    # name, we simply show a flash error message.
    description = _('Database integrity error: %s' % e)
    field = None
    related = None
    metadata = None
    constraint = getattr(e, 'constraint', None)
    if constraint and obj and obj.__table__.name in constraint.info:
        metadata = constraint.info.get(obj.__table__.name)
    elif constraint and obj and constraint.table == obj.__table__:
        metadata = constraint.info
    if metadata:
        # If availabe use metdata for specific model_name.
        description = metadata.get('description', description)
        if obj and '{' in description:
            description = description.format(obj=obj)
        field = metadata.get('field', None)
        related = _fetch_related(metadata.get('related', None), obj)
    else:
        field_match = re.search(r'Key \((.+?)\)', error) or re.search(r'.+\.(.+)', error)
        if field_match:
            field = field_match[1]

    _show_error(description=description, field=field, related=related, form=form)


def _show_rule_error(e, form=None, obj=None):
    """
    Show Rule error.
    """
    # When severity if "enforced", we must attach the message to the field directly so it get displayed as invalid-feedback.
    # Otherwise, we simply use flash message.
    field = e.field if e.severity == Rule.SEVERITY_ENFORCED else None
    level = 'error' if e.severity == Rule.SEVERITY_ENFORCED else 'warning'
    # If "other" is provided, generate a link accordingly.
    related = _fetch_related(e.related, obj)
    _show_error(
        description=e.description,
        field=field,
        level=level,
        related=related,
        form=form,
    )


def _show_error(description, field=None, related=None, level='error', form=None):
    """
    description: error description
    field: optional field name
    related: related object
    form: optional form to attach the error.
    """

    # From data collected, create an error message for the user.
    message = description
    # Append list of related records if provided.
    if related:
        # Related could be a single object or a list of objects.
        if not isinstance(related, list):
            related = [related]
        for obj in related:
            # From time to time, a record may have no summary. So provide a default value for the label.
            try:
                message += Markup(' <a href="%s">%s</a>') % (
                    url_for(obj, 'edit'),
                    obj.summary or _('Show related record'),
                )
            except ValueError:
                message += f" {obj.summary}"

    if form and field in form:
        # Add message to form if field exists.
        form_field = getattr(form, field, None)
        form_field.errors = list(form_field.errors)
        form_field.errors.append(message)
    elif field:
        # Otherwise, repport error as flash.
        flash(message + _(' Field(s): ') + field, level=level)
    else:
        flash(message, level=level)


def _fetch_related(func, obj):
    """
    Safely fetch related record.
    """
    if not func or not obj:
        return None
    assert hasattr(func, '__call__')
    try:
        return func(obj)
    except Exception:
        logger.warning('error retreiving related record(s)', exc_info=1)
        return None


def _get_context(e):

    # PostgreSQL : When using named params use it
    if isinstance(e.params, dict):
        return e.params

    # Search fields from SQL statement
    fields = []
    if e.statement.startswith('INSERT INTO'):
        match = re.match(r'INSERT INTO [^ ]+ \((.*)\) VALUES', e.statement)
        if match:
            fields = match[1].split(', ')
    elif e.statement.startswith('UPDATE'):
        fields = re.findall(r' ([^ ]+)\s?=\s?\?', e.statement)

    # Rebuild the context as dictionary
    values = e.params
    if len(fields) == len(values):
        return dict(zip(fields, values))

    return None


def validate_int(value, message=None, min=None, max=None):
    """
    Raise HTTP Error if the value is not an integer
    """
    try:
        value = int(value)
        if min and value < min:
            raise cherrypy.HTTPError(400, message)
        if max and value > max:
            raise cherrypy.HTTPError(400, message)
        return value
    except ValueError:
        raise cherrypy.HTTPError(400, message)
