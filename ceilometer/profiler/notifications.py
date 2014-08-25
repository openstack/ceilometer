# Copyright 2014: Mirantis Inc.
# All Rights Reserved.
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

from oslo.config import cfg
import oslo.messaging

from ceilometer import plugin
from ceilometer import sample


OPTS = [
    cfg.StrOpt('trove_control_exchange',
               default='trove',
               help="Exchange name for DBaaS notifications"),
]

cfg.CONF.register_opts(OPTS)
# TODO(boris-42): remove after adding keystone audit plugins.
cfg.CONF.import_opt('keystone_control_exchange',
                    'ceilometer.identity.notifications')


class ProfilerNotifications(plugin.NotificationBase):

    event_types = ["profiler.*"]

    def get_targets(self, conf):
        """Return a sequence of oslo.messaging.Target

        It is defining the exchange and topics to be connected for this plugin.
        :param conf: Configuration.
        """
        targets = []
        exchanges = [
            conf.nova_control_exchange,
            conf.cinder_control_exchange,
            conf.glance_control_exchange,
            conf.neutron_control_exchange,
            conf.heat_control_exchange,
            conf.keystone_control_exchange,
            conf.sahara_control_exchange,
            conf.trove_control_exchange,
        ]

        for exchange in exchanges:
            targets.extend(oslo.messaging.Target(topic=topic,
                                                 exchange=exchange)
                           for topic in conf.notification_topics)
        return targets

    def process_notification(self, message):
        yield sample.Sample.from_notification(
            name=message["payload"]["name"],
            type=sample.TYPE_GAUGE,
            volume=1,
            unit="trace",
            user_id=message["payload"].get("user_id"),
            project_id=message["payload"].get("project_id"),
            resource_id="profiler-%s" % message["payload"]["base_id"],
            message=message)
