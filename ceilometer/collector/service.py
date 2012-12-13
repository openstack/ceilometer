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

from stevedore import dispatch

from ceilometer.collector import meter
from ceilometer import extension_manager
from ceilometer import pipeline
from ceilometer import service
from ceilometer import storage
from ceilometer.openstack.common import context
from ceilometer.openstack.common import cfg
from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils
from ceilometer.openstack.common.rpc import dispatcher as rpc_dispatcher


OPTS = [
    cfg.ListOpt('disabled_notification_listeners',
                default=[],
                help='list of listener plugins to disable',
                ),
]

cfg.CONF.register_opts(OPTS)


LOG = log.getLogger(__name__)


class CollectorService(service.PeriodicService):

    COLLECTOR_NAMESPACE = 'ceilometer.collector'

    def start(self):
        super(CollectorService, self).start()

        storage.register_opts(cfg.CONF)
        self.storage_engine = storage.get_engine(cfg.CONF)
        self.storage_conn = self.storage_engine.get_connection(cfg.CONF)

    def initialize_service_hook(self, service):
        '''Consumers must be declared before consume_thread start.'''
        publisher_manager = dispatch.NameDispatchExtensionManager(
            namespace=pipeline.PUBLISHER_NAMESPACE,
            check_func=lambda x: True,
            invoke_on_load=True,
        )
        self.pipeline_manager = pipeline.setup_pipeline(publisher_manager)

        self.notification_manager = \
            extension_manager.ActivatedExtensionManager(
                namespace=self.COLLECTOR_NAMESPACE,
                disabled_names=cfg.CONF.disabled_notification_listeners,
            )

        if not list(self.notification_manager):
            LOG.warning('Failed to load any notification handlers for %s',
                        self.COLLECTOR_NAMESPACE)
        self.notification_manager.map(self._setup_subscription)

        # Set ourselves up as a separate worker for the metering data,
        # since the default for service is to use create_consumer().
        self.conn.create_worker(
            cfg.CONF.metering_topic,
            rpc_dispatcher.RpcDispatcher([self]),
            'ceilometer.collector.' + cfg.CONF.metering_topic,
        )

    def _setup_subscription(self, ext, *args, **kwds):
        handler = ext.obj
        LOG.debug('Event types from %s: %s',
                  ext.name, ', '.join(handler.get_event_types()))
        for exchange_topic in handler.get_exchange_topics(cfg.CONF):
            for topic in exchange_topic.topics:
                # FIXME(dhellmann): Should be using create_worker(), except
                # that notification messages do not conform to the RPC
                # invocation protocol (they do not include a "method"
                # parameter).
                self.conn.declare_topic_consumer(
                    queue_name="ceilometer.notifications",
                    topic=topic,
                    exchange_name=exchange_topic.exchange,
                    callback=self.process_notification,
                )

    def process_notification(self, notification):
        """Make a notification processed by an handler."""
        LOG.debug('notification %r', notification.get('event_type'))
        self.notification_manager.map(self._process_notification_for_ext,
                                      notification=notification,
                                      )

    def _process_notification_for_ext(self, ext, notification):
        handler = ext.obj
        if notification['event_type'] in handler.get_event_types():
            for c in handler.process_notification(notification):
                LOG.info('COUNTER: %s', c)
                # FIXME(dhellmann): Spawn green thread?
                self.publish_counter(c)

    def publish_counter(self, counter):
        """Create a metering message for the counter and publish it."""
        ctxt = context.get_admin_context()
        self.pipeline_manager.publish_counter(ctxt, counter,
                                              cfg.CONF.counter_source)

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

    def periodic_tasks(self, context):
        pass
