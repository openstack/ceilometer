#
# Copyright 2015 Red Hat. All Rights Reserved.
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

import oslo.messaging
from oslo_config import cfg

from ceilometer.agent import plugin_base
from ceilometer import sample

OPTS = [
    cfg.StrOpt('swift_control_exchange',
               default='swift',
               help="Exchange name for Swift notifications."),
]


cfg.CONF.register_opts(OPTS)


class _Base(plugin_base.NotificationBase):
    """Convert objectstore notification into Samples."""

    @staticmethod
    def get_targets(conf):
        """Return a sequence of oslo.messaging.Target

        Sequence defining the exchange and topics to be connected for this
        plugin.
        """
        return [oslo.messaging.Target(topic=topic,
                                      exchange=conf.swift_control_exchange)
                for topic in conf.notification_topics]


class SwiftWsgiMiddleware(_Base):

    def event_types(self):
        return ['objectstore.http.request']

    def process_notification(self, message):
        if message['payload']['measurements']:
            for meter in message['payload']['measurements']:
                yield sample.Sample.from_notification(
                    name=meter['metric']['name'],
                    type=sample.TYPE_DELTA,
                    unit=meter['metric']['unit'],
                    volume=meter['result'],
                    resource_id=message['payload']['target']['id'],
                    user_id=message['payload']['initiator']['id'],
                    project_id=message['payload']['initiator']['project_id'],
                    message=message)
        yield sample.Sample.from_notification(
            name='storage.api.request',
            type=sample.TYPE_DELTA,
            unit='request',
            volume=1,
            resource_id=message['payload']['target']['id'],
            user_id=message['payload']['initiator']['id'],
            project_id=message['payload']['initiator']['project_id'],
            message=message)
