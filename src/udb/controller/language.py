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

from udb.tools.i18n import gettext as _
from udb.tools.i18n import preferred_lang


@cherrypy.tools.auth_form(on=False)
@cherrypy.tools.auth_mfa(on=False)
@cherrypy.tools.currentuser(on=False)
@cherrypy.tools.db(on=False)
@cherrypy.tools.i18n(on=False)
@cherrypy.tools.ratelimit(on=False)
@cherrypy.tools.secure_headers(on=False)
@cherrypy.tools.sessions(on=False)
class Language:
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def default(self, lang, **kwargs):
        """
        Return the language file to be loaded by datatable.
        """
        with preferred_lang(lang):
            status_map = {
                "0": _("Deleted"),
                "1": _("Disabled"),
                "2": _("Enabled"),
            }
            return {
                "aria": {
                    "sortAscending": _('activate to sort column ascending'),
                    "sortDescending": _('activate to sort column descending'),
                },
                "paginate": {"previous": _('Previous'), "next": _('Next')},
                "udb": {
                    "years": _('%d years ago'),
                    "months": _('%d months ago'),
                    "days": _('%d days ago'),
                    "hours": _('%d hours ago'),
                    "minutes": _('%d minutes ago'),
                    "seconds": _('%d seconds ago'),
                    "status": {
                        "deleted": _('Deleted'),
                        "disabled": _('Disabled'),
                    },
                    "null": _('undefined'),
                    "value": {
                        "type": {
                            "new": _('Created by'),
                            "dirty": _('Modified by'),
                            "comment": _('Comment on'),
                            "parent": _('Parent modified by'),
                        },
                        "status": status_map,
                        "subnet_estatus": status_map,
                        "dnszone_estatus": status_map,
                        "severity": {
                            "0": _("No"),
                            "1": _("Yes"),
                        },
                        "dhcp": {
                            "false": _("No"),
                            "true": _("Yes"),
                        },
                        "mfa": {
                            "0": _("Disabled"),
                            "1": _("Enabled"),
                        },
                        "password": {"unknown": _("unknown")},
                    },
                    "field": {
                        "status": _("Status"),
                        "vrf": _("VRF"),
                        "owner": _("Owner"),
                        "name": _("Name"),
                        "type": _("Type"),
                        "ttl": _("TTL"),
                        "value": _("Value"),
                        "notes": _("Notes"),
                        "range": _('Primary range'),
                        "slave_subnets": _("Secondary Ranges"),
                        "l3vni": _("L3VNI"),
                        "l2vni": _("L2VNI"),
                        "vlan": _("VLAN"),
                        "rir_status": _("RIR Status"),
                        "dnszones": _("Allowed DNS zone(s)"),
                        "related_dns_records": _("Related DNS Records"),
                        "related_dhcp_records": _("Related DHCP Reservations"),
                        "related_subnets": _("Supernets"),
                        "subnets": _("Allowed subnets"),
                        "ip": _("IP"),
                        "mac": _("MAC"),
                        "statement": _("SQL Statement"),
                        "model_name": _("Data Type"),
                        "builtin": _("Built-in"),
                        "severity": _("Enforced"),
                        "username": _("Username"),
                        "password": _("Password"),
                        "role": _("Role"),
                        "fullname": _("Fullname"),
                        "email": _("Email"),
                        "lang": _("Preferred Language"),
                        "timezone": _("Preferred Time zone"),
                        "mfa": _("Two-Factor authentication"),
                        "subnet_range": _("Parent Subnet"),
                        "subnet_estatus": _("Parent Subnet status"),
                        "dhcp": _("DHCP Enabled"),
                        "dhcp_start_ip": _("DHCP Start Range"),
                        "dhcp_end_ip": _("DHCP End Range"),
                        "dnszone_estatus": _("Parent DNS Zone status"),
                    },
                },
                "info": _('Showing total of _TOTAL_'),
                "infoFiltered": _('(filtered from _MAX_ total entries)'),
                "infoEmpty": _('- No records available'),
                "lengthMenu": _('Show _MENU_ entries'),
                "processing": _('Loading...'),
                "search": _('Filter: '),
                "zeroRecords": _('List is empty'),
            }
