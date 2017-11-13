#
# Copyright 2017 Red Hat, Inc.
# Copyright 2012-2013 eNovance <licensing@enovance.com>
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

import itertools
import threading
import time
import uuid

from ceilometer.agent import plugin_base
from concurrent import futures
import cotyledon
from futurist import periodics
from oslo_config import cfg
from oslo_log import log
import oslo_messaging
from stevedore import extension
from tooz import coordination

from ceilometer.event import endpoint as event_endpoint
from ceilometer.i18n import _
from ceilometer import messaging
from ceilometer import pipeline
from ceilometer import utils


LOG = log.getLogger(__name__)


OPTS = [
    cfg.IntOpt('pipeline_processing_queues',
               default=10,
               min=1,
               help='Number of queues to parallelize workload across. This '
                    'value should be larger than the number of active '
                    'notification agents for optimal results. WARNING: '
                    'Once set, lowering this value may result in lost data.'),
    cfg.BoolOpt('ack_on_event_error',
                default=True,
                deprecated_group='collector',
                help='Acknowledge message when event persistence fails.'),
    cfg.BoolOpt('workload_partitioning',
                default=False,
                help='Enable workload partitioning, allowing multiple '
                     'notification agents to be run simultaneously.'),
    cfg.MultiStrOpt('messaging_urls',
                    default=[],
                    secret=True,
                    help="Messaging URLs to listen for notifications. "
                         "Example: rabbit://user:pass@host1:port1"
                         "[,user:pass@hostN:portN]/virtual_host "
                         "(DEFAULT/transport_url is used if empty). This "
                         "is useful when you have dedicate messaging nodes "
                         "for each service, for example, all nova "
                         "notifications go to rabbit-nova:5672, while all "
                         "cinder notifications go to rabbit-cinder:5672."),
    cfg.IntOpt('batch_size',
               default=100, min=1,
               help='Number of notification messages to wait before '
               'publishing them. Batching is advised when transformations are '
               'applied in pipeline.'),
    cfg.IntOpt('batch_timeout',
               default=5,
               help='Number of seconds to wait before publishing samples '
               'when batch_size is not reached (None means indefinitely)'),
    cfg.IntOpt('workers',
               default=1,
               min=1,
               deprecated_group='DEFAULT',
               deprecated_name='notification_workers',
               help='Number of workers for notification service, '
               'default value is 1.')
]


EXCHANGES_OPTS = [
    cfg.MultiStrOpt('notification_control_exchanges',
                    default=['nova', 'glance', 'neutron', 'cinder', 'heat',
                             'keystone', 'sahara', 'trove', 'zaqar', 'swift',
                             'ceilometer', 'magnum', 'dns'],
                    deprecated_group='DEFAULT',
                    deprecated_name="http_control_exchanges",
                    help="Exchanges name to listen for notifications."),
]


class NotificationService(cotyledon.Service):
    """Notification service.

    When running multiple agents, additional queuing sequence is required for
    inter process communication. Each agent has two listeners: one to listen
    to the main OpenStack queue and another listener(and notifier) for IPC to
    divide pipeline sink endpoints. Coordination should be enabled to have
    proper active/active HA.
    """

    NOTIFICATION_NAMESPACE = 'ceilometer.notification'
    NOTIFICATION_IPC = 'ceilometer-pipe'

    def __init__(self, worker_id, conf, coordination_id=None):
        super(NotificationService, self).__init__(worker_id)
        self.startup_delay = worker_id
        self.conf = conf

        self.periodic = None
        self.shutdown = False
        self.listeners = []
        # NOTE(kbespalov): for the pipeline queues used a single amqp host
        # hence only one listener is required
        self.pipeline_listener = None

        if self.conf.notification.workload_partitioning:
            # XXX uuid4().bytes ought to work, but it requires ascii for now
            coordination_id = (coordination_id or
                               str(uuid.uuid4()).encode('ascii'))
            self.partition_coordinator = coordination.get_coordinator(
                self.conf.coordination.backend_url, coordination_id)
            self.partition_set = list(range(
                self.conf.notification.pipeline_processing_queues))
            self.group_state = None
        else:
            self.partition_coordinator = None

    @classmethod
    def _get_notifications_manager(cls, pm):
        return extension.ExtensionManager(
            namespace=cls.NOTIFICATION_NAMESPACE,
            invoke_on_load=True,
            invoke_args=(pm, )
        )

    def _get_notifiers(self, transport, pipe):
        notifiers = []
        for x in range(self.conf.notification.pipeline_processing_queues):
            notifiers.append(oslo_messaging.Notifier(
                transport,
                driver=self.conf.publisher_notifier.telemetry_driver,
                publisher_id=pipe.name,
                topics=['%s-%s-%s' % (self.NOTIFICATION_IPC, pipe.name, x)]))
        return notifiers

    def _get_pipe_manager(self, transport, pipeline_manager):

        if self.conf.notification.workload_partitioning:
            pipe_manager = pipeline.SamplePipelineTransportManager(self.conf)
            for pipe in pipeline_manager.pipelines:
                key = pipeline.get_pipeline_grouping_key(pipe)
                pipe_manager.add_transporter(
                    (pipe.source.support_meter, key or ['resource_id'],
                     self._get_notifiers(transport, pipe)))
        else:
            pipe_manager = pipeline_manager

        return pipe_manager

    def _get_event_pipeline_manager(self, transport):
        if self.conf.notification.workload_partitioning:
            event_pipe_manager = pipeline.EventPipelineTransportManager(
                self.conf)
            for pipe in self.event_pipeline_manager.pipelines:
                event_pipe_manager.add_transporter(
                    (pipe.source.support_event, ['event_type'],
                     self._get_notifiers(transport, pipe)))
        else:
            event_pipe_manager = self.event_pipeline_manager

        return event_pipe_manager

    def run(self):
        # Delay startup so workers are jittered
        time.sleep(self.startup_delay)

        super(NotificationService, self).run()
        self.coord_lock = threading.Lock()

        self.pipeline_manager = pipeline.setup_pipeline(self.conf)

        self.event_pipeline_manager = pipeline.setup_event_pipeline(self.conf)

        self.transport = messaging.get_transport(self.conf)

        if self.conf.notification.workload_partitioning:
            self.partition_coordinator.start(start_heart=True)
        else:
            # FIXME(sileht): endpoint uses the notification_topics option
            # and it should not because this is an oslo_messaging option
            # not a ceilometer. Until we have something to get the
            # notification_topics in another way, we must create a transport
            # to ensure the option has been registered by oslo_messaging.
            messaging.get_notifier(self.transport, '')

        pipe_manager = self._get_pipe_manager(self.transport,
                                              self.pipeline_manager)
        event_pipe_manager = self._get_event_pipeline_manager(self.transport)

        self._configure_main_queue_listeners(pipe_manager, event_pipe_manager)

        if self.conf.notification.workload_partitioning:
            # join group after all manager set up is configured
            self.hashring = self.partition_coordinator.join_partitioned_group(
                self.NOTIFICATION_NAMESPACE)

            @periodics.periodic(spacing=self.conf.coordination.check_watchers,
                                run_immediately=True)
            def run_watchers():
                self.partition_coordinator.run_watchers()
                if self.group_state != self.hashring.ring.nodes:
                    self.group_state = self.hashring.ring.nodes.copy()
                    self._refresh_agent()

            self.periodic = periodics.PeriodicWorker.create(
                [], executor_factory=lambda:
                futures.ThreadPoolExecutor(max_workers=10))
            self.periodic.add(run_watchers)
            utils.spawn_thread(self.periodic.start)

    def _configure_main_queue_listeners(self, pipe_manager,
                                        event_pipe_manager):
        notification_manager = self._get_notifications_manager(pipe_manager)
        if not list(notification_manager):
            LOG.warning(_('Failed to load any notification handlers for %s'),
                        self.NOTIFICATION_NAMESPACE)

        ack_on_error = self.conf.notification.ack_on_event_error

        endpoints = []
        endpoints.append(
            event_endpoint.EventsNotificationEndpoint(event_pipe_manager))

        targets = []
        for ext in notification_manager:
            handler = ext.obj
            LOG.debug('Event types from %(name)s: %(type)s'
                      ' (ack_on_error=%(error)s)',
                      {'name': ext.name,
                       'type': ', '.join(handler.event_types),
                       'error': ack_on_error})
            # NOTE(gordc): this could be a set check but oslo_messaging issue
            # https://bugs.launchpad.net/oslo.messaging/+bug/1398511
            # This ensures we don't create multiple duplicate consumers.
            for new_tar in handler.get_targets(self.conf):
                if new_tar not in targets:
                    targets.append(new_tar)
            endpoints.append(handler)

        urls = self.conf.notification.messaging_urls or [None]
        for url in urls:
            transport = messaging.get_transport(self.conf, url)
            # NOTE(gordc): ignore batching as we want pull
            # to maintain sequencing as much as possible.
            listener = messaging.get_batch_notification_listener(
                transport, targets, endpoints)
            listener.start(
                override_pool_size=self.conf.max_parallel_requests
            )
            self.listeners.append(listener)

    def _refresh_agent(self):
        with self.coord_lock:
            if self.shutdown:
                # NOTE(sileht): We are going to shutdown we everything will be
                # stopped, we should not restart them
                return
            self._configure_pipeline_listener()

    def _configure_pipeline_listener(self):
        ev_pipes = self.event_pipeline_manager.pipelines
        pipelines = self.pipeline_manager.pipelines + ev_pipes
        transport = messaging.get_transport(self.conf)
        partitioned = list(filter(
            self.hashring.belongs_to_self, self.partition_set))

        endpoints = []
        targets = []

        for pipe in pipelines:
            if isinstance(pipe, pipeline.EventPipeline):
                endpoints.append(pipeline.EventPipelineEndpoint(pipe))
            else:
                endpoints.append(pipeline.SamplePipelineEndpoint(pipe))

        for pipe_set, pipe in itertools.product(partitioned, pipelines):
            LOG.debug('Pipeline endpoint: %s from set: %s',
                      pipe.name, pipe_set)
            topic = '%s-%s-%s' % (self.NOTIFICATION_IPC,
                                  pipe.name, pipe_set)
            targets.append(oslo_messaging.Target(topic=topic))

        if self.pipeline_listener:
            self.pipeline_listener.stop()
            self.pipeline_listener.wait()

        self.pipeline_listener = messaging.get_batch_notification_listener(
            transport,
            targets,
            endpoints,
            batch_size=self.conf.notification.batch_size,
            batch_timeout=self.conf.notification.batch_timeout)
        # NOTE(gordc): set single thread to process data sequentially
        # if batching enabled.
        batch = (1 if self.conf.notification.batch_size > 1
                 else self.conf.max_parallel_requests)
        self.pipeline_listener.start(override_pool_size=batch)

    def terminate(self):
        self.shutdown = True
        if self.periodic:
            self.periodic.stop()
            self.periodic.wait()
        if self.partition_coordinator:
            self.partition_coordinator.stop()
        with self.coord_lock:
            if self.pipeline_listener:
                utils.kill_listeners([self.pipeline_listener])
            utils.kill_listeners(self.listeners)

        super(NotificationService, self).terminate()


class NotificationProcessBase(plugin_base.NotificationBase):

    def get_targets(self, conf):
        """Return a sequence of oslo_messaging.Target

        This sequence is defining the exchange and topics to be connected for
        this plugin.
        """
        return [oslo_messaging.Target(topic=topic, exchange=exchange)
                for topic in self.get_notification_topics(conf)
                for exchange in
                conf.notification.notification_control_exchanges]
