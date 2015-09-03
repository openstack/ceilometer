#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 eNovance
#
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
"""Converters for producing compute sample messages from notification events.
"""

import abc

import six

from ceilometer.agent import plugin_base
from ceilometer.compute import notifications
from ceilometer.compute import util
from ceilometer import sample


@six.add_metaclass(abc.ABCMeta)
class UserMetadataAwareInstanceNotificationBase(
        notifications.ComputeNotificationBase):
    """Consumes notifications containing instance user metadata."""

    def process_notification(self, message):
        instance_properties = self.get_instance_properties(message)
        if isinstance(instance_properties.get('metadata'), dict):
            src_metadata = instance_properties['metadata']
            del instance_properties['metadata']
            util.add_reserved_user_metadata(src_metadata, instance_properties)
        return self.get_sample(message)

    def get_instance_properties(self, message):
        """Retrieve instance properties from notification payload."""
        return message['payload']

    @abc.abstractmethod
    def get_sample(self, message):
        """Derive sample from notification payload."""


class InstanceScheduled(UserMetadataAwareInstanceNotificationBase,
                        plugin_base.NonMetricNotificationBase):
    event_types = ['scheduler.run_instance.scheduled']

    def get_instance_properties(self, message):
        """Retrieve instance properties from notification payload."""
        return message['payload']['request_spec']['instance_properties']

    def get_sample(self, message):
        yield sample.Sample.from_notification(
            name='instance.scheduled',
            type=sample.TYPE_DELTA,
            volume=1,
            unit='instance',
            user_id=None,
            project_id=message['payload']['request_spec']
                              ['instance_properties']['project_id'],
            resource_id=message['payload']['instance_id'],
            message=message)


class ComputeInstanceNotificationBase(
        UserMetadataAwareInstanceNotificationBase):
    """Convert compute.instance.* notifications into Samples."""
    event_types = ['compute.instance.*']


class Instance(ComputeInstanceNotificationBase,
               plugin_base.NonMetricNotificationBase):
    def get_sample(self, message):
        yield sample.Sample.from_notification(
            name='instance',
            type=sample.TYPE_GAUGE,
            unit='instance',
            volume=1,
            user_id=message['payload']['user_id'],
            project_id=message['payload']['tenant_id'],
            resource_id=message['payload']['instance_id'],
            message=message)
