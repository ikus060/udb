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
from sqlalchemy import Column, ForeignKey, and_, func, or_, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declared_attr, foreign, relationship, remote
from sqlalchemy.types import JSON, Integer, SmallInteger, String, Text

import udb.tools.db  # noqa: import cherrypy.tools.db

from ._common import CommonMixin
from ._dhcprecord import DhcpRecord
from ._dnsrecord import DnsRecord
from ._json import JsonMixin
from ._message import Message, MessageMixin
from ._search_string import SearchableMixing
from ._status import StatusMixing
from ._subnet import Subnet
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
    model_name = Column(String, nullable=False, server_default='')
    start_id = Column(Integer, nullable=False)
    end_id = Column(Integer, nullable=False)
    change_count = Column(Integer, nullable=False)
    state = Column(SmallInteger, nullable=False, default=STATE_STARTING)
    data = Column(JSON, nullable=False)
    output = Column(Text, nullable=False, default='')
    token = Column(String, nullable=False, default=lambda: binascii.hexlify(os.urandom(20)).decode('ascii'))

    @declared_attr
    def changes(cls):
        """
        Return a list of changes deployed by this deployment.
        """
        return relationship(
            Message,
            primaryjoin=and_(
                Message.type.in_([Message.TYPE_NEW, Message.TYPE_DIRTY]),
                or_(
                    # Include any changes made to related model
                    cls.model_name == remote(foreign(Message.model_name)),
                    # Include change made to environment it self.
                    and_(Message.model_name == 'environment', cls.id == remote(foreign(Message.model_id))),
                ),
                cls.start_id <= remote(foreign(Message.id)),
                cls.end_id >= remote(foreign(Message.id)),
            ),
            lazy=True,
            viewonly=True,
        )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Query the types to persist.
        self.model_name = (
            Environment.query.with_entities(Environment.model_name)
            .filter(Environment.id == self.environment_id)
            .scalar()
        )
        # Take a snapshot of the data within the deployment.
        if self.model_name == 'subnet':
            subnet = (
                Subnet.query.with_entities(
                    Subnet.id,
                    Vrf.name.label('vrf'),
                    Subnet.l3vni,
                    Subnet.l2vni,
                    Subnet.vlan,
                    func.group_concat(Subnet.range.text()),
                )
                .join(Subnet.vrf)
                .filter(Subnet.estatus == Subnet.STATUS_ENABLED)
                .group_by(Subnet.id, Vrf.name)
                .all()
            )
            self.data = {'subnet': [s._asdict() for s in subnet]}
        elif self.model_name == 'dnsrecord':
            dnsrecord = (
                DnsRecord.query.with_entities(
                    DnsRecord.id,
                    DnsRecord.type,
                    DnsRecord.name,
                    DnsRecord.ttl,
                    DnsRecord.value,
                )
                .filter(DnsRecord.estatus == DnsRecord.STATUS_ENABLED)
                .all()
            )
            self.data = {'dnsrecord': [s._asdict() for s in dnsrecord]}
        elif self.model_name == 'dhcprecord':
            # TODO Migth be better to move that into DHCP model.
            # TODO using relationship or similar.

            # Return DHCP member of a Subnet with DHCP enabled.
            subnet_query = select(
                Subnet.id,
                Subnet.name,
                Subnet.l2vni,
                Subnet.l3vni,
                Subnet.vlan,
                Subnet.range,
                Subnet.dhcp,
                Subnet.dhcp_start_ip,
                Subnet.dhcp_end_ip,
            ).filter(
                Subnet.dhcp.is_(True),
                Subnet.estatus == Subnet.STATUS_ENABLED,
            )
            # Identify the subnet related for each dhcp record.
            related_subnet_query = (
                select(Subnet.id)
                .filter(
                    Subnet.dhcp.is_(True),
                    Subnet.estatus == Subnet.STATUS_ENABLED,
                    Subnet.dhcp_start_ip <= DhcpRecord.ip,
                    Subnet.dhcp_end_ip >= DhcpRecord.ip,
                )
                .scalar_subquery()
            )
            # Identify the hostname for each dhcp record.
            hostname_query = (
                select(DnsRecord.value)
                .filter(
                    DnsRecord.type == 'PTR',
                    DnsRecord.generated_ip == DhcpRecord.ip,
                    DnsRecord.estatus == DnsRecord.STATUS_ENABLED,
                )
                .scalar_subquery()
            )
            dhcp_query = select(
                DhcpRecord.id,
                DhcpRecord.ip,
                DhcpRecord.mac,
                related_subnet_query.label('subnet_range_id'),
                # TODO must be tested
                hostname_query.label('hostname'),
            ).filter(
                DhcpRecord.estatus == DhcpRecord.STATUS_ENABLED,
            )
            self.data = {
                'dhcprecord': [s._asdict() for s in DhcpRecord.session.execute(dhcp_query).all()],
                'slave_subnets': [s._asdict() for s in Subnet.session.execute(subnet_query).all()],
            }
        else:
            raise ValueError('unsupported model_name: %s' % self.model_name)

    def schedule_task(self, base_url):
        """
        Used to schedule this deployment.

        URL to the deployment data must be provided by the controller.
        """
        assert self.id, 'deployment must be commit'
        assert self.state == Deployment.STATE_STARTING, 'cannot schedule deployment twice'
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

    @declared_attr
    def pending_changes(cls):
        """
        Return a list of changes (new or dirty message) that was not part of a previous deployment.
        """
        return relationship(
            Message,
            primaryjoin=and_(
                Message.type.in_([Message.TYPE_NEW, Message.TYPE_DIRTY]),
                or_(
                    # Include any changes made to related model
                    cls.model_name == remote(foreign(Message.model_name)),
                    # Include change made to environment it self.
                    and_(Message.model_name == 'environment', cls.id == remote(foreign(Message.model_id))),
                ),
                Message.id.__gt__(
                    func.coalesce(
                        select(func.max(Deployment.end_id))
                        .filter(Deployment.environment_id == cls.id, Deployment.model_name == cls.model_name)
                        .scalar_subquery(),
                        0,
                    )
                ),
            ),
            lazy=True,
            viewonly=True,
        )

    def create_deployment(self, owner):
        """
        Create a new deployment for this environment.
        """
        assert owner and owner.id, 'deployment required a owner'
        # Identify changes
        row = (
            Environment.query.with_entities(
                func.coalesce(func.min(Message.id), -1).label('start_id'),
                func.coalesce(func.max(Message.id), -1).label('end_id'),
                func.count(Message.id).label('count'),
            )
            .join(Environment.pending_changes)
            .filter(Environment.id == self.id)
            .first()
        )
        return Deployment(
            environment_id=self.id,
            change_count=row.count,
            start_id=row.start_id,
            end_id=row.end_id,
            owner=owner,
        )

    @classmethod
    def count_pending_changes(cls, limit=10):
        return Environment.query.with_entities(func.count(Message.id)).join(Environment.pending_changes).scalar()
