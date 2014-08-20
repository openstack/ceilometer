# Copyright (c) 2014 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from oslo.config import cfg
import oslo.messaging

from ceilometer import plugin
from ceilometer import sample


OPTS = [
    cfg.StrOpt('sahara_control_exchange',
               default='sahara',
               help="Exchange name for Data Processing notifications"),
]

cfg.CONF.register_opts(OPTS)
SERVICE = 'sahara'


class DataProcessing(plugin.NotificationBase):

    resource_name = '%s.cluster' % SERVICE

    @property
    def event_types(self):
        return [
            '%s.create' % self.resource_name,
            '%s.update' % self.resource_name,
            '%s.delete' % self.resource_name,
        ]

    @staticmethod
    def get_targets(conf):
        """Return a sequence of oslo.messaging.Target

        It is defining the exchange and topics to be connected for this plugin.
        """
        return [oslo.messaging.Target(topic=topic,
                                      exchange=conf.sahara_control_exchange)
                for topic in conf.notification_topics]

    def process_notification(self, message):
        name = message['event_type'].replace(self.resource_name, 'cluster')

        project_id = message['payload']['project_id']

        user_id = message['_context_user_id']

        yield sample.Sample.from_notification(
            name=name,
            type=sample.TYPE_DELTA,
            unit='cluster',
            volume=1,
            resource_id=message['payload']['cluster_id'],
            user_id=user_id,
            project_id=project_id,
            message=message)
