#
# Copyright 2013 Intel
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

from ceilometer.agent import plugin_base


OPTS = [
    cfg.StrOpt('nova_control_exchange',
               default='nova',
               help="Exchange name for Nova notifications."),
]


cfg.CONF.register_opts(OPTS)


class ComputeNotificationBase(plugin_base.NotificationBase):
    def get_targets(self, conf):
        """Return a sequence of oslo_messaging.Target

        This sequence is defining the exchange and topics to be connected for
        this plugin.
        """
        return [oslo_messaging.Target(topic=topic,
                                      exchange=conf.nova_control_exchange)
                for topic in self.get_notification_topics(conf)]
