#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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
"""Converters for producing volume counter messages from cinder notification
events.
"""

from oslo_config import cfg
import oslo_messaging

from ceilometer.agent import plugin_base
from ceilometer import sample

OPTS = [
    cfg.StrOpt('cinder_control_exchange',
               default='cinder',
               help="Exchange name for Cinder notifications."),
]


cfg.CONF.register_opts(OPTS)


class VolumeBase(plugin_base.NotificationBase):
    """Convert volume/snapshot notification into Counters."""

    @staticmethod
    def get_targets(conf):
        """Return a sequence of oslo.messaging.Target

        Sequence defining the exchange and topics to be connected for this
        plugin.
        """
        return [oslo_messaging.Target(topic=topic,
                                      exchange=conf.cinder_control_exchange)
                for topic in conf.notification_topics]


class VolumeCRUDBase(VolumeBase):
    """Convert volume notifications into Counters."""

    event_types = [
        'volume.exists',
        'volume.create.*',
        'volume.delete.*',
        'volume.resize.*',
        'volume.attach.*',
        'volume.detach.*',
        'volume.update.*'
    ]


class VolumeCRUD(VolumeCRUDBase, plugin_base.NonMetricNotificationBase):
    def process_notification(self, message):
        yield sample.Sample.from_notification(
            name=message['event_type'],
            type=sample.TYPE_DELTA,
            unit='volume',
            volume=1,
            user_id=message['payload']['user_id'],
            project_id=message['payload']['tenant_id'],
            resource_id=message['payload']['volume_id'],
            message=message)


class Volume(VolumeCRUDBase, plugin_base.NonMetricNotificationBase):
    def process_notification(self, message):
        yield sample.Sample.from_notification(
            name='volume',
            type=sample.TYPE_GAUGE,
            unit='volume',
            volume=1,
            user_id=message['payload']['user_id'],
            project_id=message['payload']['tenant_id'],
            resource_id=message['payload']['volume_id'],
            message=message)


class VolumeSize(VolumeCRUDBase):
    def process_notification(self, message):
        yield sample.Sample.from_notification(
            name='volume.size',
            type=sample.TYPE_GAUGE,
            unit='GB',
            volume=message['payload']['size'],
            user_id=message['payload']['user_id'],
            project_id=message['payload']['tenant_id'],
            resource_id=message['payload']['volume_id'],
            message=message)


class SnapshotCRUDBase(VolumeBase):
    """Convert snapshot notifications into Counters."""

    event_types = [
        'snapshot.exists',
        'snapshot.create.*',
        'snapshot.delete.*',
        'snapshot.update.*'
    ]


class SnapshotCRUD(SnapshotCRUDBase, plugin_base.NonMetricNotificationBase):
    def process_notification(self, message):
        yield sample.Sample.from_notification(
            name=message['event_type'],
            type=sample.TYPE_DELTA,
            unit='snapshot',
            volume=1,
            user_id=message['payload']['user_id'],
            project_id=message['payload']['tenant_id'],
            resource_id=message['payload']['snapshot_id'],
            message=message)


class Snapshot(SnapshotCRUDBase, plugin_base.NonMetricNotificationBase):
    def process_notification(self, message):
        yield sample.Sample.from_notification(
            name='snapshot',
            type=sample.TYPE_GAUGE,
            unit='snapshot',
            volume=1,
            user_id=message['payload']['user_id'],
            project_id=message['payload']['tenant_id'],
            resource_id=message['payload']['snapshot_id'],
            message=message)


class SnapshotSize(SnapshotCRUDBase):
    def process_notification(self, message):
        yield sample.Sample.from_notification(
            name='snapshot.size',
            type=sample.TYPE_GAUGE,
            unit='GB',
            volume=message['payload']['volume_size'],
            user_id=message['payload']['user_id'],
            project_id=message['payload']['tenant_id'],
            resource_id=message['payload']['snapshot_id'],
            message=message)
