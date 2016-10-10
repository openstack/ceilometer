#
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

from concurrent import futures
from futurist import periodics
from oslo_config import cfg
from oslo_log import log
import oslo_messaging
from stevedore import extension

from ceilometer.agent import plugin_base as base
from ceilometer import coordination
from ceilometer.event import endpoint as event_endpoint
from ceilometer import exchange_control
from ceilometer.i18n import _, _LI, _LW
from ceilometer import messaging
from ceilometer import pipeline
from ceilometer import service_base
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
    cfg.BoolOpt('disable_non_metric_meters',
                default=True,
                help='WARNING: Ceilometer historically offered the ability to '
                     'store events as meters. This usage is NOT advised as it '
                     'can flood the metering database and cause performance '
                     'degradation.'),
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
               'publishing them. Batching is advised when transformations are'
               'applied in pipeline.'),
    cfg.IntOpt('batch_timeout',
               default=5,
               help='Number of seconds to wait before publishing samples'
               'when batch_size is not reached (None means indefinitely)'),
]

cfg.CONF.register_opts(exchange_control.EXCHANGE_OPTS)
cfg.CONF.register_opts(OPTS, group="notification")
cfg.CONF.import_opt('telemetry_driver', 'ceilometer.publisher.messaging',
                    group='publisher_notifier')


class NotificationService(service_base.PipelineBasedService):
    """Notification service.

    When running multiple agents, additional queuing sequence is required for
    inter process communication. Each agent has two listeners: one to listen
    to the main OpenStack queue and another listener(and notifier) for IPC to
    divide pipeline sink endpoints. Coordination should be enabled to have
    proper active/active HA.
    """

    NOTIFICATION_NAMESPACE = 'ceilometer.notification'
    NOTIFICATION_IPC = 'ceilometer-pipe'

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
        super(NotificationService, self).run()
        self.shutdown = False
        self.periodic = None
        self.partition_coordinator = None
        self.coord_lock = threading.Lock()

        self.listeners = []

        # NOTE(kbespalov): for the pipeline queues used a single amqp host
        # hence only one listener is required
        self.pipeline_listener = None

        self.pipeline_manager = pipeline.setup_pipeline(self.conf)

        self.event_pipeline_manager = pipeline.setup_event_pipeline(self.conf)

        self.transport = messaging.get_transport(self.conf)

        if self.conf.notification.workload_partitioning:
            self.group_id = self.NOTIFICATION_NAMESPACE
            self.partition_coordinator = coordination.PartitionCoordinator(
                self.conf)
            self.partition_coordinator.start()
        else:
            # FIXME(sileht): endpoint uses the notification_topics option
            # and it should not because this is an oslo_messaging option
            # not a ceilometer. Until we have something to get the
            # notification_topics in another way, we must create a transport
            # to ensure the option has been registered by oslo_messaging.
            messaging.get_notifier(self.transport, '')
            self.group_id = None

        self.pipe_manager = self._get_pipe_manager(self.transport,
                                                   self.pipeline_manager)
        self.event_pipe_manager = self._get_event_pipeline_manager(
            self.transport)

        self._configure_main_queue_listeners(self.pipe_manager,
                                             self.event_pipe_manager)

        if self.conf.notification.workload_partitioning:
            # join group after all manager set up is configured
            self.partition_coordinator.join_group(self.group_id)
            self.partition_coordinator.watch_group(self.group_id,
                                                   self._refresh_agent)

            @periodics.periodic(spacing=self.conf.coordination.heartbeat,
                                run_immediately=True)
            def heartbeat():
                self.partition_coordinator.heartbeat()

            @periodics.periodic(spacing=self.conf.coordination.check_watchers,
                                run_immediately=True)
            def run_watchers():
                self.partition_coordinator.run_watchers()

            self.periodic = periodics.PeriodicWorker.create(
                [], executor_factory=lambda:
                futures.ThreadPoolExecutor(max_workers=10))
            self.periodic.add(heartbeat)
            self.periodic.add(run_watchers)

            utils.spawn_thread(self.periodic.start)

            # configure pipelines after all coordination is configured.
            with self.coord_lock:
                self._configure_pipeline_listener()

        if not self.conf.notification.disable_non_metric_meters:
            LOG.warning(_LW('Non-metric meters may be collected. It is highly '
                            'advisable to disable these meters using '
                            'ceilometer.conf or the pipeline.yaml'))

        self.init_pipeline_refresh()

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
            if (self.conf.notification.disable_non_metric_meters and
                    isinstance(handler, base.NonMetricNotificationBase)):
                continue
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
            listener.start()
            self.listeners.append(listener)

    def _refresh_agent(self, event):
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
        partitioned = self.partition_coordinator.extract_my_subset(
            self.group_id,
            range(self.conf.notification.pipeline_processing_queues))

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
        batch = (1 if self.conf.notification.batch_size > 1 else None)
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

    def reload_pipeline(self):
        LOG.info(_LI("Reloading notification agent and listeners."))

        if self.pipeline_validated:
            self.pipe_manager = self._get_pipe_manager(
                self.transport, self.pipeline_manager)

        if self.event_pipeline_validated:
            self.event_pipe_manager = self._get_event_pipeline_manager(
                self.transport)

        with self.coord_lock:
            if self.shutdown:
                # NOTE(sileht): We are going to shutdown we everything will be
                # stopped, we should not restart them
                return

            # restart the main queue listeners.
            utils.kill_listeners(self.listeners)
            self._configure_main_queue_listeners(
                self.pipe_manager, self.event_pipe_manager)

            # restart the pipeline listeners if workload partitioning
            # is enabled.
            if self.conf.notification.workload_partitioning:
                self._configure_pipeline_listener()
