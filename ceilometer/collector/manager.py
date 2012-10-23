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

import functools
import itertools
import pkg_resources

from nova import context
from nova import manager

from ceilometer import meter
from ceilometer import publish
from ceilometer import storage
from ceilometer.openstack.common import cfg
from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils
from ceilometer.openstack.common.rpc import dispatcher as rpc_dispatcher

try:
    import ceilometer.openstack.common.rpc as rpc
except ImportError:
    # For Essex
    import nova.rpc as rpc


LOG = log.getLogger(__name__)


class CollectorManager(manager.Manager):

    COLLECTOR_NAMESPACE = 'ceilometer.collector'

    @staticmethod
    def _load_plugins(plugin_namespace):
        handlers = []
        # Listen for notifications from nova
        for ep in pkg_resources.iter_entry_points(plugin_namespace):
            LOG.info('attempting to load notification handler for %s:%s',
                     plugin_namespace, ep.name)
            try:
                # FIXME(dhellmann): Currently assumes all plugins are
                # enabled when they are discovered and
                # importable. Need to add check against global
                # configuration flag and check that asks the plugin if
                # it should be enabled.
                plugin_class = ep.load()
                plugin = plugin_class()
                handlers.append(plugin)
            except Exception as err:
                LOG.warning('Failed to load notification handler %s: %s',
                            ep.name, err)
                LOG.exception(err)
        return handlers

    def init_host(self):
        # Use the nova configuration flags to get
        # a connection to the RPC mechanism nova
        # is using.
        self.connection = rpc.create_connection()

        storage.register_opts(cfg.CONF)
        self.storage_engine = storage.get_engine(cfg.CONF)
        self.storage_conn = self.storage_engine.get_connection(cfg.CONF)

        self.handlers = self._load_plugins(self.COLLECTOR_NAMESPACE)

        if not self.handlers:
            LOG.warning('Failed to load any notification handlers for %s',
                        self.plugin_namespace)

        # FIXME(dhellmann): Should be using create_worker(), except
        # that notification messages do not conform to the RPC
        # invocation protocol (they do not include a "method"
        # parameter).
        # FIXME(dhellmann): Break this out into its own method
        # so we can test the subscription logic.
        for handler in self.handlers:
            LOG.debug('Event types: %r', handler.get_event_types())
            for exchange_topic in handler.get_exchange_topics(cfg.CONF):
                for topic in exchange_topic.topics:
                    self.connection.declare_topic_consumer(
                        queue_name="ceilometer.notifications",
                        topic=topic,
                        exchange_name=exchange_topic.exchange,
                        callback=self.process_notification,
                        )

        # Set ourselves up as a separate worker for the metering data,
        # since the default for manager is to use create_consumer().
        self.connection.create_worker(
            cfg.CONF.metering_topic,
            rpc_dispatcher.RpcDispatcher([self]),
            'ceilometer.collector.' + cfg.CONF.metering_topic,
            )

        self.connection.consume_in_thread()

    def process_notification(self, notification):
        """Make a notification processed by an handler."""
        LOG.debug('notification %r', notification.get('event_type'))
        for handler in self.handlers:
            if notification['event_type'] in handler.get_event_types():
                for c in handler.process_notification(notification):
                    LOG.info('COUNTER: %s', c)
                    # FIXME(dhellmann): Spawn green thread?
                    self.publish_counter(c)

    @staticmethod
    def publish_counter(counter):
        """Create a metering message for the counter and publish it."""
        ctxt = context.get_admin_context()
        publish.publish_counter(ctxt, counter,
            cfg.CONF.metering_topic, cfg.CONF.metering_secret,
            )

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
        if not meter.verify_signature(data, cfg.CONF.metering_secret):
            LOG.warning('message signature invalid, discarding message: %r',
                        data)
        else:
            try:
                # Convert the timestamp to a datetime instance.
                # Storage engines are responsible for converting
                # that value to something they can store.
                if data.get('timestamp'):
                    ts = timeutils.parse_isotime(data['timestamp'])
                    data['timestamp'] = timeutils.normalize_time(ts)
                self.storage_conn.record_metering_data(data)
            except Exception as err:
                LOG.error('Failed to record metering data: %s', err)
                LOG.exception(err)
