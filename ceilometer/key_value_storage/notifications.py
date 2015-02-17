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
    cfg.StrOpt('magnetodb_control_exchange',
               default='magnetodb',
               help="Exchange name for Magnetodb notifications."),
]


cfg.CONF.register_opts(OPTS)


class _Base(plugin_base.NotificationBase):
    """Convert magnetodb notification into Samples."""

    @staticmethod
    def get_targets(conf):
        """Return a sequence of oslo.messaging.Target

        Sequence defining the exchange and topics to be connected for this
        plugin.
        """
        return [oslo.messaging.Target(topic=topic,
                                      exchange=conf.magnetodb_control_exchange)
                for topic in conf.notification_topics]


class Table(_Base, plugin_base.NonMetricNotificationBase):

    event_types = [
        'magnetodb.table.create.end',
        'magnetodb.table.delete.end'
    ]

    def process_notification(self, message):
        meter_name = '.'.join(message['event_type'].split('.')[:-1])
        yield sample.Sample.from_notification(
            name=meter_name,
            type=sample.TYPE_GAUGE,
            unit='table',
            volume=1,
            resource_id=message['payload']['table_uuid'],
            user_id=message['_context_user'],
            project_id=message['_context_tenant'],
            message=message)


class Index(_Base):

    event_types = [
        'magnetodb.table.create.end'
    ]

    def process_notification(self, message):
        yield sample.Sample.from_notification(
            name='magnetodb.table.index.count',
            type=sample.TYPE_GAUGE,
            unit='index',
            volume=message['payload']['index_count'],
            resource_id=message['payload']['table_uuid'],
            user_id=message['_context_user'],
            project_id=message['_context_tenant'],
            message=message)
