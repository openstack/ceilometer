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

import oslo_messaging

from ceilometer.agent import plugin_base
from ceilometer import sample


class TelemetryBase(plugin_base.NotificationBase):
    """Convert telemetry notification into Samples."""

    def get_targets(self, conf):
        """Return a sequence of oslo_messaging.Target

        Sequence defining the exchange and topics to be connected for this
        plugin.
        """
        return [oslo_messaging.Target(
                topic=topic, exchange=conf.ceilometer_control_exchange)
                for topic in self.get_notification_topics(conf)]


class TelemetryIpc(TelemetryBase):
    """Handle sample from notification bus

     Telemetry samples can be posted via API or polled by Polling agent.
     """

    event_types = ['telemetry.api', 'telemetry.polling']

    def process_notification(self, message):
        samples = message['payload']['samples']
        for sample_dict in samples:
            yield sample.Sample(
                name=sample_dict['counter_name'],
                type=sample_dict['counter_type'],
                unit=sample_dict['counter_unit'],
                volume=sample_dict['counter_volume'],
                user_id=sample_dict['user_id'],
                project_id=sample_dict['project_id'],
                resource_id=sample_dict['resource_id'],
                timestamp=sample_dict['timestamp'],
                resource_metadata=sample_dict['resource_metadata'],
                source=sample_dict['source'],
                id=sample_dict['message_id'])
