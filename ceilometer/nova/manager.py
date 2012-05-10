# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
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

from nova import log as logging
from nova import manager
from nova import flags

# Import rabbit_notifier to register notification_topics flag
import nova.notifier.rabbit_notifier

from ceilometer import rpc

FLAGS = flags.FLAGS
LOG = logging.getLogger(__name__)


class InstanceManager(manager.Manager):
    def init_host(self):
        self.connection = rpc.Connection(flags.FLAGS)
        self.connection.declare_topic_consumer(
            topic='%s.info' % flags.FLAGS.notification_topics[0],
            callback=self._on_notification)
        self.connection.consume_in_thread()

    def _on_notification(self, body):
        event_type = body.get('event_type')
        LOG.info('NOTIFICATION: %s', event_type)
