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

from oslo.config import cfg

from ceilometer.collector import meter as meter_api
from ceilometer import extension_manager
from ceilometer.openstack.common import context
from ceilometer.openstack.common import log
from ceilometer.openstack.common.rpc import dispatcher as rpc_dispatcher

# Import rpc_notifier to register `notification_topics` flag so that
# plugins can use it
# FIXME(dhellmann): Use option importing feature of oslo.config instead.
import ceilometer.openstack.common.notifier.rpc_notifier

from ceilometer.openstack.common import timeutils
from ceilometer import pipeline
from ceilometer import publisher
from ceilometer import service
from ceilometer import storage
from ceilometer import transformer

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
        LOG.debug('initialize_service_hooks')
        self.pipeline_manager = pipeline.setup_pipeline(
            transformer.TransformerExtensionManager(
                'ceilometer.transformer',
            ),
            publisher.PublisherExtensionManager(
                'ceilometer.publisher',
            ),
        )

        LOG.debug('loading notification handlers from %s',
                  self.COLLECTOR_NAMESPACE)
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
                try:
                    self.conn.join_consumer_pool(
                        callback=self.process_notification,
                        pool_name='ceilometer.notifications',
                        topic=topic,
                        exchange_name=exchange_topic.exchange,
                    )
                except Exception:
                    LOG.exception('Could not join consumer pool %s/%s' %
                                  (topic, exchange_topic.exchange))

    def process_notification(self, notification):
        """Make a notification processed by an handler."""
        LOG.debug('notification %r', notification.get('event_type'))
        self.notification_manager.map(self._process_notification_for_ext,
                                      notification=notification,
                                      )

    def _process_notification_for_ext(self, ext, notification):
        handler = ext.obj
        if notification['event_type'] in handler.get_event_types():
            ctxt = context.get_admin_context()
            with self.pipeline_manager.publisher(ctxt,
                                                 cfg.CONF.counter_source) as p:
                # FIXME(dhellmann): Spawn green thread?
                p(list(handler.process_notification(notification)))

    def record_metering_data(self, context, data):
        """This method is triggered when metering data is
        cast from an agent.
        """
        # We may have receive only one counter on the wire
        if not isinstance(data, list):
            data = [data]

        for meter in data:
            LOG.info('metering data %s for %s @ %s: %s',
                     meter['counter_name'],
                     meter['resource_id'],
                     meter.get('timestamp', 'NO TIMESTAMP'),
                     meter['counter_volume'])
            if meter_api.verify_signature(meter, cfg.CONF.metering_secret):
                try:
                    # Convert the timestamp to a datetime instance.
                    # Storage engines are responsible for converting
                    # that value to something they can store.
                    if meter.get('timestamp'):
                        ts = timeutils.parse_isotime(meter['timestamp'])
                        meter['timestamp'] = timeutils.normalize_time(ts)
                    self.storage_conn.record_metering_data(meter)
                except Exception as err:
                    LOG.error('Failed to record metering data: %s', err)
                    LOG.exception(err)
            else:
                LOG.warning(
                    'message signature invalid, discarding message: %r',
                    meter)

    def periodic_tasks(self, context):
        pass
