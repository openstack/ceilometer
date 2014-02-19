# Author: Swann Croiset <swann.croiset@bull.net>
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
"""Handler for producing orchestration metering from Heat notification
   events.
"""

from oslo.config import cfg

from ceilometer import plugin
from ceilometer import sample


OPTS = [
    cfg.StrOpt('heat_control_exchange',
               default='heat',
               help="Exchange name for Heat notifications"),
]

cfg.CONF.register_opts(OPTS)
SERVICE = 'orchestration'


class StackCRUD(plugin.NotificationBase):

    resource_name = '%s.stack' % SERVICE

    @property
    def event_types(self):
        return [
            '%s.create.end' % (self.resource_name),
            '%s.update.end' % (self.resource_name),
            '%s.delete.end' % (self.resource_name),
            '%s.resume.end' % (self.resource_name),
            '%s.suspend.end' % (self.resource_name),
        ]

    @staticmethod
    def get_exchange_topics(conf):
        return [
            plugin.ExchangeTopics(
                exchange=conf.heat_control_exchange,
                topics=set(topic + ".info"
                           for topic in conf.notification_topics)),
        ]

    def process_notification(self, message):
        name = message['event_type']                \
            .replace(self.resource_name, 'stack')   \
            .replace('.end', '')

        project_id = message['payload']['tenant_id']

        # Trying to use the trustor_id if trusts is used by Heat,
        user_id = message.get('_context_trustor_user_id') or \
            message['_context_user_id']

        yield sample.Sample.from_notification(
            name=name,
            type=sample.TYPE_DELTA,
            unit='stack',
            volume=1,
            resource_id=message['payload']['stack_identity'],
            user_id=user_id,
            project_id=project_id,
            message=message)
