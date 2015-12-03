#
# Copyright 2015 Hewlett Packard
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

from oslo_config import cfg
import oslo_messaging
from oslo_utils import timeutils

from ceilometer.agent import plugin_base
from ceilometer import sample

OPTS = [
    cfg.StrOpt('dns_control_exchange',
               default='central',
               help="Exchange name for DNS notifications."),

]

cfg.CONF.register_opts(OPTS)
SERVICE = 'dns'


class DnsMetricsNotificationBase(plugin_base.NotificationBase):
    """Base class for DNSaaS(Designate) notifications."""

    def get_targets(self, conf):
        """Return a sequence of oslo.messaging.Target

        This sequence is defining the exchange and topics to be connected for
        this plugin.
        """
        return [oslo_messaging.Target(topic=topic,
                                      exchange=conf.dns_control_exchange)
                for topic in self.get_notification_topics(conf)]


class DomainExists(DnsMetricsNotificationBase):
    """Handles DNS domain exists notification.

    Emits a sample for a measurable audit interval.
    """

    event_types = ['%s.domain.exists' % SERVICE]

    def process_notification(self, message):

        period_start = timeutils.normalize_time(timeutils.parse_isotime(
            message['payload']['audit_period_beginning']))
        period_end = timeutils.normalize_time(timeutils.parse_isotime(
            message['payload']['audit_period_ending']))

        period_difference = timeutils.delta_seconds(period_start, period_end)

        yield sample.Sample.from_notification(
            name=message['event_type'],
            type=sample.TYPE_CUMULATIVE,
            unit='s',
            volume=period_difference,
            resource_id=message['payload']['id'],
            user_id=message['_context_user'],
            project_id=message['payload']['tenant_id'],
            message=message)
