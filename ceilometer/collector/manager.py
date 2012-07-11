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

from nova import context
from nova import flags
from nova import manager

from ceilometer import meter
from ceilometer import publish
from ceilometer import rpc
from ceilometer import storage
from ceilometer.collector import dispatcher
from ceilometer.openstack.common import cfg
from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils
from ceilometer.openstack.common.rpc import dispatcher as rpc_dispatcher

# FIXME(dhellmann): There must be another way to do this.
# Import rabbit_notifier to register notification_topics flag
import ceilometer.openstack.common.notifier.rabbit_notifier
try:
    import nova.openstack.common.rpc as nova_rpc
except ImportError:
    # For Essex
    import nova.rpc as nova_rpc

LOG = log.getLogger(__name__)


COMPUTE_COLLECTOR_NAMESPACE = 'ceilometer.collector.compute'


class CollectorManager(manager.Manager):

    def init_host(self):
        # Use the nova configuration flags to get
        # a connection to the RPC mechanism nova
        # is using.
        self.connection = nova_rpc.create_connection()

        storage.register_opts(cfg.CONF)
        self.storage_engine = storage.get_engine(cfg.CONF)
        self.storage_conn = self.storage_engine.get_connection(cfg.CONF)

        self.compute_handler = dispatcher.NotificationDispatcher(
            COMPUTE_COLLECTOR_NAMESPACE,
            self._publish_counter,
            )
        # FIXME(dhellmann): Should be using create_worker(), except
        # that notification messages do not conform to the RPC
        # invocation protocol (they do not include a "method"
        # parameter).
        self.connection.declare_topic_consumer(
            topic='%s.info' % flags.FLAGS.notification_topics[0],
            callback=self.compute_handler.notify)

        # Set ourselves up as a separate worker for the metering data,
        # since the default for manager is to use create_consumer().
        self.connection.create_worker(
            cfg.CONF.metering_topic,
            rpc_dispatcher.RpcDispatcher([self]),
            'ceilometer.collector.' + cfg.CONF.metering_topic,
            )

        self.connection.consume_in_thread()

    def _publish_counter(self, counter):
        """Create a metering message for the counter and publish it."""
        ctxt = context.get_admin_context()
        publish.publish_counter(ctxt, counter)

    def record_metering_data(self, context, data):
        """This method is triggered when metering data is
        cast from an agent.
        """
        #LOG.info('metering data: %r', data)
        LOG.info('metering data %s for %s @ %s: %s',
                 data['counter_name'],
                 data['resource_id'],
                 data.get('timestamp', 'NO TIMESTAMP'),
                 data['counter_volume'])
        if not meter.verify_signature(data):
            LOG.warning('message signature invalid, discarding message: %r',
                        data)
        else:
            try:
                # Convert the timestamp to a datetime instance.
                # Storage engines are responsible for converting
                # that value to something they can store.
                if 'timestamp' in data:
                    data['timestamp'] = timeutils.parse_isotime(
                        data['timestamp'],
                        )
                self.storage_conn.record_metering_data(data)
            except Exception as err:
                LOG.error('Failed to record metering data: %s', err)
                LOG.exception(err)
