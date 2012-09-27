# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Julien Danjou <julien@danjou.info>
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
"""Handler for producing network counter messages from Quantum notification
   events.

"""

from ceilometer import counter
from ceilometer import plugin
from ceilometer.openstack.common import cfg


OPTS = [
    cfg.StrOpt('quantum_control_exchange',
               default='quantum',
               help="Exchange name for Quantum notifications"),
]


cfg.CONF.register_opts(OPTS)


class NetworkNotificationBase(plugin.NotificationBase):

    def get_event_types(self):
        return [
            '%s.create.end' % (self.resource_name, event),
            '%s.update.end' % (self.resource_name, event),
            '%s.delete.start' % (self.resource_name, event),
        ]

    @staticmethod
    def get_exchange_topics(conf):
        """Return a sequence of ExchangeTopics defining the exchange and
        topics to be connected for this plugin."""
        return [
            plugin.ExchangeTopics(
                exchange=conf.quantum_control_exchange,
                topics=set(topic + ".info"
                           for topic in conf.notification_topics)),
        ]

    def process_notification(self, message):
        message['payload'] = message['payload'][self.resource_name]
        return [
            counter.Counter(source='?',
                            name=self.resource_name,
                            type='absolute',
                            volume=1,
                            user_id=message['_context_user_id'],
                            project_id=message['payload']['tenant_id'],
                            resource_id=message['payload']['id'],
                            timestamp=message['timestamp'],
                            duration=None,
                            resource_metadata=self.notification_to_metadata(
                                message),
                        ),
        ]


class Network(NetworkNotificationBase):
    """Listen for Quantum network notifications in order to mediate with the
    metering framework.

    """

    metadata_keys = [
        "status",
        "subnets",
        "name",
        "router:external",
        "admin_state_up",
        "shared",
    ]

    resource_name = 'network'


class Subnet(NetworkNotificationBase):
    """Listen for Quantum notifications in order to mediate with the
    metering framework.

    """

    metadata_keys = [
        "name",
        "enable_dhcp",
        "network_id",
        "dns_nameservers",
        "allocation_pools",
        "host_routes",
        "ip_version",
        "gateway_ip",
        "cidr",
    ]

    resource_name = 'subnet'


class Port(NetworkNotificationBase):
    """Listen for Quantum notifications in order to mediate with the
    metering framework.

    """

    metadata_keys = [
        "status",
        "name",
        "admin_state_up",
        "network_id",
        "device_owner",
        "mac_address",
        "fixed_ips",
        "device_id",
    ]

    resource_name = 'port'
