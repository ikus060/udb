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


import binascii
import os
import shutil
import subprocess
import sys
import tempfile

import cherrypy
from sqlalchemy import Column, ForeignKey, func
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON, Integer, SmallInteger, String, Text

import udb.tools.db  # noqa: import cherrypy.tools.db

from ._common import CommonMixin
from ._dhcprecord import DhcpRecord
from ._dnsrecord import DnsRecord
from ._json import JsonMixin
from ._message import MessageMixin
from ._search_string import SearchableMixing
from ._status import StatusMixing
from ._subnet import Subnet, SubnetRange
from ._vrf import Vrf

Base = cherrypy.tools.db.get_base()


def _deploy(deployment_id, base_url):
    """
    Called by the scheduler to execute the deployment.
    """
    # Get the deployment object
    deployment = Deployment.query.filter(Deployment.id == deployment_id).one()
    deployment.state = Deployment.STATE_RUNNING
    deployment.commit()

    # TODO Execute script a nobody Maybe using a Jail ?

    # Create a temporary folder
    working_dir = tempfile.mkdtemp(prefix='udb-deployment-%s-' % deployment.id)

    try:
        # Switch permissions to nobody when running as root on Python>=3.9
        kwargs = {}
        if sys.version_info[0:2] >= (3, 9) and os.getuid() == 0:
            kwargs = {'user': 65534, 'group': 65534}
        # Define environment variables.
        env = {
            "UDB_USERID": str(deployment.owner.id),
            "UDB_USERNAME": deployment.owner.username,
            "UDB_DEPLOYMENT_ID": str(deployment.id),
            "UDB_DEPLOYMENT_TOKEN": deployment.token,
            "UDB_DEPLOYMENT_AUTH": "%s:%s" % (deployment.owner.username, deployment.token),
            "UDB_DEPLOYMENT_MODEL_NAME": deployment.environment.model_name,
            "UDB_DEPLOYMENT_DATA_URL": cherrypy.url("api/deployment/%s" % deployment.id, base=base_url),
        }
        # Start the process with bash.
        process = subprocess.Popen(
            '/bin/bash',
            env=env,
            cwd=working_dir,
            start_new_session=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            **kwargs
        )
        # Write script using "newline" instead of "cariage return"
        script = deployment.environment.script.replace('\r\n', '\n').encode('utf8')
        process.stdin.write(script)
        process.stdin.close()
        # Read output.
        while True:
            line = process.stdout.readline(65365)
            if not line:
                break
            # Obfuscate deployment token and store output to database
            line = line.decode('utf-8').replace(deployment.token, '********')
            deployment.output += line
            deployment.commit()
        process.wait()
        if process.returncode != 0:
            deployment.output += '\nreturn code: %s' % process.returncode
            deployment.output += '\nFAILED'
            deployment.state = Deployment.STATE_FAILURE
        else:
            deployment.output += '\nSUCCESS'
            deployment.state = Deployment.STATE_SUCCESS
        deployment.commit()
    except Exception as e:
        deployment.output += '\n' + str(e)
        deployment.output += '\nFAILED'
        deployment.state = Deployment.STATE_FAILURE
        deployment.commit()
    finally:
        # Delete temporary folder
        shutil.rmtree(working_dir, ignore_errors=True)


class Deployment(CommonMixin, JsonMixin, Base):
    """
    A Deployment represent a Job ran to deploy changes.
    """

    STATE_STARTING = 0
    STATE_RUNNING = 1
    STATE_SUCCESS = 2
    STATE_FAILURE = 3

    environment_id = Column(Integer, ForeignKey("environment.id"), nullable=False)
    environment = relationship("Environment", back_populates='deployments', lazy=True)
    start_id = Column(Integer, nullable=False)
    end_id = Column(Integer, nullable=False)
    change_count = Column(Integer, nullable=False)
    state = Column(SmallInteger, nullable=False, default=STATE_STARTING)
    data = Column(JSON, nullable=False)
    output = Column(Text, nullable=False, default='')
    token = Column(String, nullable=False, default=lambda: binascii.hexlify(os.urandom(20)).decode('ascii'))

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Query the types to persist.
        model_name = (
            Environment.query.with_entities(Environment.model_name)
            .filter(Environment.id == self.environment_id)
            .scalar()
        )
        # Take a snapshot of the data within the deployment.
        if model_name == 'subnet':
            subnet = (
                Subnet.query.with_entities(
                    Subnet.id,
                    Vrf.name.label('vrf'),
                    Subnet.l3vni,
                    Subnet.l2vni,
                    Subnet.vlan,
                    func.group_concat(SubnetRange.range.text()),
                )
                .join(Subnet.vrf)
                .join(Subnet.subnet_ranges)
                .filter(Subnet.status == Subnet.STATUS_ENABLED)
                .group_by(Subnet.id)
                .all()
            )
            self.data = {'subnet': [s._asdict() for s in subnet]}
        elif model_name == 'dnsrecord':
            dnsrecord = (
                DnsRecord.query.with_entities(
                    DnsRecord.id,
                    DnsRecord.type,
                    DnsRecord.name,
                    DnsRecord.ttl,
                    DnsRecord.value,
                )
                .filter(DnsRecord.status == DnsRecord.STATUS_ENABLED)
                .all()
            )
            self.data = {'dnsrecord': [s._asdict() for s in dnsrecord]}
        elif model_name == 'dhcprecord':
            dhcprecord = (
                DhcpRecord.query.with_entities(
                    DhcpRecord.id,
                    DhcpRecord.ip,
                    DhcpRecord.mac,
                )
                .filter(DhcpRecord.status == DhcpRecord.STATUS_ENABLED)
                .all()
            )
            self.data = {'dhcprecord': [s._asdict() for s in dhcprecord]}
        else:
            raise ValueError('unsuported model_name: %s' % model_name)

    def schedule_task(self, base_url):
        """
        Used to schedule this deployment.

        URL to the deployment data must be provided by the controller.
        """
        if self.state != Deployment.STATE_STARTING:
            raise ValueError('Cannot schedule a deployment twice.')
        # Detach the object from the session. Otherwise it cause trouble with multi-threading.
        cherrypy.engine.publish('schedule_task', _deploy, self.id, base_url)

    def to_json(self):
        return {
            'id': self.id,
            'change_count': self.change_count,
            'created_at': self.created_at.isoformat(),
            'start_id': self.start_id,
            'end_id': self.end_id,
            'state': self.state,
            'environment_id': self.environment_id,
        }


class Environment(CommonMixin, JsonMixin, MessageMixin, StatusMixing, SearchableMixing, Base):
    name = Column(String, nullable=False)
    script = Column(Text, nullable=False, default='')
    model_name = Column(String, nullable=False)
    deployments = relationship("Deployment", back_populates='environment', lazy=True)

    @classmethod
    def _search_string(cls):
        return cls.name

    @hybrid_property
    def summary(self):
        return self.name
