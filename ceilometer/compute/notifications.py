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


class InstanceNotifications(plugin.NotificationBase):
    """Convert compute.instance.* notifications into Counters
    """

    @staticmethod
    def get_event_types():
        return ['compute.instance.create.end',
                'compute.instance.exists',
                'compute.instance.delete.start',
                ]

    @staticmethod
    def process_notification(message):
        return [counter.Counter(
            source='?',
            name='instance',
            type='cumulative',
            volume=1,
            user_id=message['payload']['user_id'],
            project_id=message['payload']['tenant_id'],
            resource_id=message['payload']['instance_id'],
            timestamp=message['timestamp'],
            duration=0,
            resource_metadata=instance.get_metadata_from_event(message),
        )]
