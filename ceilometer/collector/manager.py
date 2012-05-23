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

from nova import flags
from nova import log as logging
from nova import manager

from ceilometer import rpc
from ceilometer import meter
from ceilometer.collector import dispatcher

# FIXME(dhellmann): There must be another way to do this.
# Import rabbit_notifier to register notification_topics flag
import nova.notifier.rabbit_notifier

FLAGS = flags.FLAGS
# FIXME(dhellmann): We need to have the main program set up logging
# correctly so messages from modules outside of the nova package
# appear in the output.
LOG = logging.getLogger('nova.' + __name__)


COMPUTE_COLLECTOR_NAMESPACE = 'ceilometer.collector.compute'


class CollectorManager(manager.Manager):
    def init_host(self):
        self.connection = rpc.Connection(flags.FLAGS)
        self.compute_handler = dispatcher.NotificationDispatcher(
            COMPUTE_COLLECTOR_NAMESPACE,
            self._publish_counter,
            )
        self.connection.declare_topic_consumer(
            topic='%s.info' % flags.FLAGS.notification_topics[0],
            callback=self.compute_handler.notify)
        self.connection.consume_in_thread()

    def _publish_counter(self, counter):
        """Create a metering message for the counter and publish it."""
        msg = meter.meter_message_from_counter(counter)
        LOG.info('PUBLISH: %s', str(msg))
        # FIXME(dhellmann): Need to publish the message on the
        # metering queue.
