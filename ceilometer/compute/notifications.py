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

INSTANCE_PROPERTIES = [
    # Identity properties
    'display_name',
    'reservation_id',
    # Type properties
    'architecture'
    # Location properties
    'availability_zone',
    # Image properties
    'image_ref',
    'image_ref_url',
    'kernel_id',
    'os_type',
    'ramdisk_id',
    # Capacity properties
    'disk_gb',
    'ephemeral_gb',
    'memory_mb',
    'root_gb',
    'vcpus',
    ]


def get_instance_metadata_from_event(body):
    """Return a metadata dictionary for the instance mentioned in the
    notification event.
    """
    instance = body['payload']
    metadata = {
        'event_type': body['event_type'],
        'instance_type': instance['instance_type_id'],
        'host': body['publisher_id'],
        }
    for name in INSTANCE_PROPERTIES:
        metadata[name] = instance.get(name, u'')
    return metadata


def c1(body):
    """Generate c1(instance) counters for a notice."""
    return counter.Counter(
        source='?',
        name='instance',
        type='delta',
        volume=1,
        user_id=body['payload']['user_id'],
        project_id=body['payload']['tenant_id'],
        resource_id=body['payload']['instance_id'],
        timestamp=body['timestamp'],
        duration=0,
        resource_metadata=get_instance_metadata_from_event(body),
        )


class InstanceNotifications(plugin.NotificationBase):
    """Convert compute.instance.* notifications into Counters
    """

    def get_event_types(self):
        return ['compute.instance.create.end',
                'compute.instance.exists',
                'compute.instance.delete.start',
                ]

    def process_notification(self, message):
        return [c1(message),
                ]
