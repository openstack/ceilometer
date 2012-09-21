# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
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
"""Converters for producing compute counter messages from notification events.
"""

from ceilometer import counter
from ceilometer import plugin
from ceilometer.compute import instance


class _Base(plugin.NotificationBase):
    """Convert compute.instance.* notifications into Counters
    """
    metadata_keys = instance.INSTANCE_PROPERTIES

    def notification_to_metadata(self, event):
        metadata = super(_Base, self).notification_to_metadata(event)
        metadata['instance_type'] = event['payload']['instance_type_id']
        return metadata

    @staticmethod
    def get_event_types():
        return ['compute.instance.create.end',
                'compute.instance.exists',
                'compute.instance.delete.start',
        ]


class Instance(_Base):

    def process_notification(self, message):
        return [
            counter.Counter(source='?',
                            name='instance',
                            type='absolute',
                            volume=1,
                            user_id=message['payload']['user_id'],
                            project_id=message['payload']['tenant_id'],
                            resource_id=message['payload']['instance_id'],
                            timestamp=message['timestamp'],
                            duration=0,
                            resource_metadata=self.notification_to_metadata(
                                message),
                            ),
            ]


class Memory(_Base):

    def process_notification(self, message):
        return [
            counter.Counter(source='?',
                            name='memory',
                            type='absolute',
                            volume=message['payload']['memory_mb'],
                            user_id=message['payload']['user_id'],
                            project_id=message['payload']['tenant_id'],
                            resource_id=message['payload']['instance_id'],
                            timestamp=message['timestamp'],
                            duration=0,
                            resource_metadata=self.notification_to_metadata(
                                message),
                        ),
            ]


class VCpus(_Base):

    def process_notification(self, message):
        return [
            counter.Counter(source='?',
                            name='vcpus',
                            type='absolute',
                            volume=message['payload']['vcpus'],
                            user_id=message['payload']['user_id'],
                            project_id=message['payload']['tenant_id'],
                            resource_id=message['payload']['instance_id'],
                            timestamp=message['timestamp'],
                            duration=0,
                            resource_metadata=self.notification_to_metadata(
                                message),
                        ),
            ]


class RootDiskSize(_Base):

    def process_notification(self, message):
        return [
            counter.Counter(source='?',
                            name='root_disk_size',
                            type='absolute',
                            volume=message['payload']['root_gb'],
                            user_id=message['payload']['user_id'],
                            project_id=message['payload']['tenant_id'],
                            resource_id=message['payload']['instance_id'],
                            timestamp=message['timestamp'],
                            duration=0,
                            resource_metadata=self.notification_to_metadata(
                                message),
                        ),
            ]


class EphemeralDiskSize(_Base):

    def process_notification(self, message):
        return [
            counter.Counter(source='?',
                            name='ephemeral_disk_size',
                            type='absolute',
                            volume=message['payload']['ephemeral_gb'],
                            user_id=message['payload']['user_id'],
                            project_id=message['payload']['tenant_id'],
                            resource_id=message['payload']['instance_id'],
                            timestamp=message['timestamp'],
                            duration=0,
                            resource_metadata=self.notification_to_metadata(
                                message),
                        ),
            ]


class InstanceFlavor(_Base):

    def process_notification(self, message):
        counters = []
        instance_type = message.get('payload', {}).get('instance_type')
        if instance_type:
            counters.append(
                counter.Counter(
                    source='?',
                    name='instance:%s' % instance_type,
                    type='absolute',
                    volume=1,
                    user_id=message['payload']['user_id'],
                    project_id=message['payload']['tenant_id'],
                    resource_id=message['payload']['instance_id'],
                    timestamp=message['timestamp'],
                    duration=0,
                    resource_metadata=self.notification_to_metadata(
                        message),
                )
            )
        return counters
