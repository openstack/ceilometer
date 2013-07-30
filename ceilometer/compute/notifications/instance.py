# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
# Copyright © 2013 eNovance
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
#         Julien Danjou <julien@danjou.info>
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

from ceilometer.compute import notifications
from ceilometer import sample


class InstanceScheduled(notifications.ComputeNotificationBase):
    event_types = ['scheduler.run_instance.scheduled']

    def process_notification(self, message):
        yield sample.Sample.from_notification(
            name='instance.scheduled',
            type=sample.TYPE_DELTA,
            volume=1,
            unit='instance',
            user_id=None,
            project_id=
            message['payload']['request_spec']
            ['instance_properties']['project_id'],
            resource_id=message['payload']['instance_id'],
            message=message)


class ComputeInstanceNotificationBase(notifications.ComputeNotificationBase):
    """Convert compute.instance.* notifications into Samples
    """
    event_types = ['compute.instance.*']


class Instance(ComputeInstanceNotificationBase):
    def process_notification(self, message):
        yield sample.Sample.from_notification(
            name='instance',
            type=sample.TYPE_GAUGE,
            unit='instance',
            volume=1,
            user_id=message['payload']['user_id'],
            project_id=message['payload']['tenant_id'],
            resource_id=message['payload']['instance_id'],
            message=message)


class Memory(ComputeInstanceNotificationBase):
    def process_notification(self, message):
        yield sample.Sample.from_notification(
            name='memory',
            type=sample.TYPE_GAUGE,
            unit='MB',
            volume=message['payload']['memory_mb'],
            user_id=message['payload']['user_id'],
            project_id=message['payload']['tenant_id'],
            resource_id=message['payload']['instance_id'],
            message=message)


class VCpus(ComputeInstanceNotificationBase):
    def process_notification(self, message):
        yield sample.Sample.from_notification(
            name='vcpus',
            type=sample.TYPE_GAUGE,
            unit='vcpu',
            volume=message['payload']['vcpus'],
            user_id=message['payload']['user_id'],
            project_id=message['payload']['tenant_id'],
            resource_id=message['payload']['instance_id'],
            message=message)


class RootDiskSize(ComputeInstanceNotificationBase):
    def process_notification(self, message):
        yield sample.Sample.from_notification(
            name='disk.root.size',
            type=sample.TYPE_GAUGE,
            unit='GB',
            volume=message['payload']['root_gb'],
            user_id=message['payload']['user_id'],
            project_id=message['payload']['tenant_id'],
            resource_id=message['payload']['instance_id'],
            message=message)


class EphemeralDiskSize(ComputeInstanceNotificationBase):
    def process_notification(self, message):
        yield sample.Sample.from_notification(
            name='disk.ephemeral.size',
            type=sample.TYPE_GAUGE,
            unit='GB',
            volume=message['payload']['ephemeral_gb'],
            user_id=message['payload']['user_id'],
            project_id=message['payload']['tenant_id'],
            resource_id=message['payload']['instance_id'],
            message=message)


class InstanceFlavor(ComputeInstanceNotificationBase):
    def process_notification(self, message):
        instance_type = message.get('payload', {}).get('instance_type')
        if instance_type:
            yield sample.Sample.from_notification(
                name='instance:%s' % instance_type,
                type=sample.TYPE_GAUGE,
                unit='instance',
                volume=1,
                user_id=message['payload']['user_id'],
                project_id=message['payload']['tenant_id'],
                resource_id=message['payload']['instance_id'],
                message=message)


class InstanceDelete(ComputeInstanceNotificationBase):
    """Handle the messages sent by the nova notifier plugin
    when an instance is being deleted.
    """

    event_types = ['compute.instance.delete.samples']

    def process_notification(self, message):
        for s in message['payload'].get('samples', []):
            yield sample.Sample.from_notification(
                name=s['name'],
                type=s['type'],
                unit=s['unit'],
                volume=s['volume'],
                user_id=message['payload']['user_id'],
                project_id=message['payload']['tenant_id'],
                resource_id=message['payload']['instance_id'],
                message=message)
