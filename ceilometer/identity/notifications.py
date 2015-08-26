# Copyright 2014 Mirantis Inc.
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import oslo.messaging
from oslo_config import cfg

from ceilometer.agent import plugin_base
from ceilometer import sample

OPTS = [
    cfg.StrOpt('keystone_control_exchange',
               default='keystone',
               help="Exchange name for Keystone notifications."),
]


cfg.CONF.register_opts(OPTS)

SERVICE = 'identity'


class _Base(plugin_base.NotificationBase,
            plugin_base.NonMetricNotificationBase):
    """Convert identity notification into Samples."""

    resource_type = None
    resource_name = None

    @staticmethod
    def get_targets(conf):
        """Return a sequence of oslo.messaging.Target

        Sequence defining the exchange and topics to be connected for this
        plugin.
        """
        return [oslo.messaging.Target(topic=topic,
                                      exchange=conf.keystone_control_exchange)
                for topic in conf.notification_topics]


class IdentityCRUD(_Base):
    def process_notification(self, message):
        user_id = message['payload'].get("initiator", {}).get("id")
        yield sample.Sample.from_notification(
            name=message['event_type'],
            type=sample.TYPE_DELTA,
            unit=self.resource_type,
            volume=1,
            resource_id=message['payload']['resource_info'],
            user_id=user_id,
            project_id=None,
            message=message)


class User(IdentityCRUD):

    resource_type = 'user'
    resource_name = '%s.%s' % (SERVICE, resource_type)

    @property
    def event_types(self):
        return ['%s.*' % self.resource_name]


class Group(IdentityCRUD):

    resource_type = 'group'
    resource_name = '%s.%s' % (SERVICE, resource_type)

    @property
    def event_types(self):
        return ['%s.*' % self.resource_name]


class Project(IdentityCRUD):

    resource_type = 'project'
    resource_name = '%s.%s' % (SERVICE, resource_type)

    @property
    def event_types(self):
        return ['%s.*' % self.resource_name]


class Role(IdentityCRUD):

    resource_type = 'role'
    resource_name = '%s.%s' % (SERVICE, resource_type)

    @property
    def event_types(self):
        return ['%s\..*' % self.resource_name]


class Trust(_Base):

    resource_type = 'OS-TRUST:trust'
    resource_name = '%s.%s' % (SERVICE, resource_type)

    @property
    def event_types(self):
        return [
            '%s.created' % self.resource_name,
            '%s.deleted' % self.resource_name,
        ]

    def process_notification(self, message):
        name = message['event_type'].replace(self.resource_type, 'trust')
        user_id = message['payload'].get("initiator", {}).get("id")
        yield sample.Sample.from_notification(
            name=name,
            type=sample.TYPE_DELTA,
            unit='trust',
            volume=1,
            resource_id=message['payload']['resource_info'],
            user_id=user_id,
            project_id=None,
            message=message)


class Authenticate(_Base):
    """Convert identity authentication notifications into Samples."""

    resource_type = 'authenticate'
    event_name = '%s.%s' % (SERVICE, resource_type)

    def process_notification(self, message):
        outcome = message['payload']['outcome']
        meter_name = '%s.%s.%s' % (SERVICE, self.resource_type, outcome)

        yield sample.Sample.from_notification(
            name=meter_name,
            type=sample.TYPE_DELTA,
            unit='user',
            volume=1,
            resource_id=message['payload']['initiator']['id'],
            user_id=message['payload']['initiator']['id'],
            project_id=None,
            message=message)

    @property
    def event_types(self):
        return [self.event_name]


class RoleAssignment(_Base):
    """Convert role assignment notifications into Samples."""

    resource_type = 'role_assignment'
    resource_name = '%s.%s' % (SERVICE, resource_type)

    def process_notification(self, message):
        # NOTE(stevemar): action is created.role_assignment
        action = message['payload']['action']
        event, resource_type = action.split(".")

        # NOTE(stevemar): meter_name is identity.role_assignment.created
        meter_name = '%s.%s.%s' % (SERVICE, resource_type, event)

        yield sample.Sample.from_notification(
            name=meter_name,
            type=sample.TYPE_DELTA,
            unit=self.resource_type,
            volume=1,
            resource_id=message['payload']['role'],
            user_id=message['payload']['initiator']['id'],
            project_id=None,
            message=message)

    @property
    def event_types(self):
        return [
            '%s.created' % self.resource_name,
            '%s.deleted' % self.resource_name,
        ]
