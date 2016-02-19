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

from oslo_config import cfg
from oslo_context import context
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
                    'notification agents for optimal results.'),
    cfg.BoolOpt('ack_on_event_error',
                default=True,
                deprecated_group='collector',
                help='Acknowledge message when event persistence fails.'),
    cfg.BoolOpt('store_events',
                deprecated_group='collector',
                default=False,
                help='Save event details.'),
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
                         "Example: transport://user:pass@host1:port"
                         "[,hostN:portN]/virtual_host "
                         "(DEFAULT/transport_url is used if empty)"),
    cfg.IntOpt('batch_size',
               default=1,
               help='Number of notification messages to wait before '
               'publishing them'),
    cfg.IntOpt('batch_timeout',
               default=None,
               help='Number of seconds to wait before publishing samples'
               'when batch_size is not reached (None means indefinitely)'),
]

cfg.CONF.register_opts(exchange_control.EXCHANGE_OPTS)
cfg.CONF.register_opts(OPTS, group="notification")
cfg.CONF.import_opt('telemetry_driver', 'ceilometer.publisher.messaging',
                    group='publisher_notifier')


class NotificationService(service_base.BaseService):
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
        for x in range(cfg.CONF.notification.pipeline_processing_queues):
            notifiers.append(oslo_messaging.Notifier(
                transport,
                driver=cfg.CONF.publisher_notifier.telemetry_driver,
                publisher_id='ceilometer.notification',
                topic='%s-%s-%s' % (self.NOTIFICATION_IPC, pipe.name, x)))
        return notifiers

    def _get_pipe_manager(self, transport, pipeline_manager):

        if cfg.CONF.notification.workload_partitioning:
            pipe_manager = pipeline.SamplePipelineTransportManager()
            for pipe in pipeline_manager.pipelines:
                key = pipeline.get_pipeline_grouping_key(pipe)
                pipe_manager.add_transporter(
                    (pipe.source.support_meter, key or ['resource_id'],
                     self._get_notifiers(transport, pipe)))
        else:
            pipe_manager = pipeline_manager

        return pipe_manager

    def _get_event_pipeline_manager(self, transport):

        if cfg.CONF.notification.store_events:
            if cfg.CONF.notification.workload_partitioning:
                event_pipe_manager = pipeline.EventPipelineTransportManager()
                for pipe in self.event_pipeline_manager.pipelines:
                    event_pipe_manager.add_transporter(
                        (pipe.source.support_event, ['event_type'],
                         self._get_notifiers(transport, pipe)))
            else:
                event_pipe_manager = self.event_pipeline_manager

            return event_pipe_manager

    def start(self):
        super(NotificationService, self).start()
        self.partition_coordinator = None
        self.coord_lock = threading.Lock()
        self.listeners, self.pipeline_listeners = [], []

        self.pipeline_manager = pipeline.setup_pipeline()

        if cfg.CONF.notification.store_events:
            self.event_pipeline_manager = pipeline.setup_event_pipeline()

        self.transport = messaging.get_transport()

        if cfg.CONF.notification.workload_partitioning:
            self.ctxt = context.get_admin_context()
            self.group_id = self.NOTIFICATION_NAMESPACE
            self.partition_coordinator = coordination.PartitionCoordinator()
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

        self.listeners, self.pipeline_listeners = [], []
        self._configure_main_queue_listeners(self.pipe_manager,
                                             self.event_pipe_manager)

        if cfg.CONF.notification.workload_partitioning:
            # join group after all manager set up is configured
            self.partition_coordinator.join_group(self.group_id)
            self.partition_coordinator.watch_group(self.group_id,
                                                   self._refresh_agent)
            self.tg.add_timer(cfg.CONF.coordination.heartbeat,
                              self.partition_coordinator.heartbeat)
            self.tg.add_timer(cfg.CONF.coordination.check_watchers,
                              self.partition_coordinator.run_watchers)
            # configure pipelines after all coordination is configured.
            self._configure_pipeline_listeners()

        if not cfg.CONF.notification.disable_non_metric_meters:
            LOG.warning(_LW('Non-metric meters may be collected. It is highly '
                            'advisable to disable these meters using '
                            'ceilometer.conf or the pipeline.yaml'))
        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)

        self.init_pipeline_refresh()

    def _configure_main_queue_listeners(self, pipe_manager,
                                        event_pipe_manager):
        notification_manager = self._get_notifications_manager(pipe_manager)
        if not list(notification_manager):
            LOG.warning(_('Failed to load any notification handlers for %s'),
                        self.NOTIFICATION_NAMESPACE)

        ack_on_error = cfg.CONF.notification.ack_on_event_error

        endpoints = []
        if cfg.CONF.notification.store_events:
            endpoints.append(
                event_endpoint.EventsNotificationEndpoint(event_pipe_manager))

        targets = []
        for ext in notification_manager:
            handler = ext.obj
            if (cfg.CONF.notification.disable_non_metric_meters and
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
            for new_tar in handler.get_targets(cfg.CONF):
                if new_tar not in targets:
                    targets.append(new_tar)
            endpoints.append(handler)

        urls = cfg.CONF.notification.messaging_urls or [None]
        for url in urls:
            transport = messaging.get_transport(url)
            listener = messaging.get_batch_notification_listener(
                transport, targets, endpoints,
                batch_size=cfg.CONF.notification.batch_size,
                batch_timeout=cfg.CONF.notification.batch_timeout)
            listener.start()
            self.listeners.append(listener)

    def _refresh_agent(self, event):
        self._configure_pipeline_listeners(True)

    def _configure_pipeline_listeners(self, reuse_listeners=False):
        with self.coord_lock:
            ev_pipes = []
            if cfg.CONF.notification.store_events:
                ev_pipes = self.event_pipeline_manager.pipelines
            pipelines = self.pipeline_manager.pipelines + ev_pipes
            transport = messaging.get_transport()
            partitioned = self.partition_coordinator.extract_my_subset(
                self.group_id,
                range(cfg.CONF.notification.pipeline_processing_queues))

            queue_set = {}
            for pipe_set, pipe in itertools.product(partitioned, pipelines):
                queue_set['%s-%s-%s' %
                          (self.NOTIFICATION_IPC, pipe.name, pipe_set)] = pipe

            if reuse_listeners:
                topics = queue_set.keys()
                kill_list = []
                for listener in self.pipeline_listeners:
                    if listener.dispatcher.targets[0].topic in topics:
                        queue_set.pop(listener.dispatcher.targets[0].topic)
                    else:
                        kill_list.append(listener)
                for listener in kill_list:
                    utils.kill_listeners([listener])
                    self.pipeline_listeners.remove(listener)
            else:
                utils.kill_listeners(self.pipeline_listeners)
                self.pipeline_listeners = []

            for topic, pipe in queue_set.items():
                LOG.debug('Pipeline endpoint: %s from set: %s', pipe.name,
                          pipe_set)
                pipe_endpoint = (pipeline.EventPipelineEndpoint
                                 if isinstance(pipe, pipeline.EventPipeline)
                                 else pipeline.SamplePipelineEndpoint)
                listener = messaging.get_batch_notification_listener(
                    transport,
                    [oslo_messaging.Target(topic=topic)],
                    [pipe_endpoint(self.ctxt, pipe)],
                    batch_size=cfg.CONF.notification.batch_size,
                    batch_timeout=cfg.CONF.notification.batch_timeout)
                listener.start()
                self.pipeline_listeners.append(listener)

    def stop(self):
        if getattr(self, 'partition_coordinator', None):
            self.partition_coordinator.stop()
        listeners = []
        if getattr(self, 'listeners', None):
            listeners.extend(self.listeners)
        if getattr(self, 'pipeline_listeners', None):
            listeners.extend(self.pipeline_listeners)
        utils.kill_listeners(listeners)
        super(NotificationService, self).stop()

    def reload_pipeline(self):
        LOG.info(_LI("Reloading notification agent and listeners."))

        if self.pipeline_validated:
            self.pipe_manager = self._get_pipe_manager(
                self.transport, self.pipeline_manager)

        if self.event_pipeline_validated:
            self.event_pipe_manager = self._get_event_pipeline_manager(
                self.transport)

        # re-start the main queue listeners.
        utils.kill_listeners(self.listeners)
        self._configure_main_queue_listeners(
            self.pipe_manager, self.event_pipe_manager)

        # re-start the pipeline listeners if workload partitioning
        # is enabled.
        if cfg.CONF.notification.workload_partitioning:
            self._configure_pipeline_listeners()
