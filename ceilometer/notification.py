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

from oslo_config import cfg
from oslo_context import context
from oslo_log import log
import oslo_messaging
from stevedore import extension

from ceilometer.agent import plugin_base as base
from ceilometer import coordination
from ceilometer.event import endpoint as event_endpoint
from ceilometer.i18n import _, _LI, _LW
from ceilometer import messaging
from ceilometer import pipeline
from ceilometer import service_base
from ceilometer import utils


LOG = log.getLogger(__name__)


OPTS = [
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
                    help="Messaging URLs to listen for notifications. "
                         "Example: transport://user:pass@host1:port"
                         "[,hostN:portN]/virtual_host "
                         "(DEFAULT/transport_url is used if empty)"),
]

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

    def __init__(self, *args, **kwargs):
        super(NotificationService, self).__init__(*args, **kwargs)
        self.partition_coordinator = None
        self.listeners, self.pipeline_listeners = [], []
        self.group_id = None

    @classmethod
    def _get_notifications_manager(cls, pm):
        return extension.ExtensionManager(
            namespace=cls.NOTIFICATION_NAMESPACE,
            invoke_on_load=True,
            invoke_args=(pm, )
        )

    def _get_notifiers(self, transport, pipe):
        notifiers = []
        for agent in self.partition_coordinator._get_members(self.group_id):
            notifiers.append(oslo_messaging.Notifier(
                transport,
                driver=cfg.CONF.publisher_notifier.telemetry_driver,
                publisher_id='ceilometer.notification',
                topic='%s-%s-%s' % (self.NOTIFICATION_IPC, pipe.name, agent)))
        return notifiers

    def _get_pipe_manager(self, transport, pipeline_manager):

        if cfg.CONF.notification.workload_partitioning:
            pipe_manager = pipeline.SamplePipelineTransportManager()
            for pipe in pipeline_manager.pipelines:
                pipe_manager.add_transporter(
                    (pipe.source.support_meter,
                     self._get_notifiers(transport, pipe)))
        else:
            pipe_manager = pipeline_manager

        return pipe_manager

    def _get_event_pipeline_manager(self, transport):

        if cfg.CONF.notification.store_events:
            self.event_pipeline_manager = pipeline.setup_event_pipeline()

            if cfg.CONF.notification.workload_partitioning:
                event_pipe_manager = pipeline.EventPipelineTransportManager()
                for pipe in self.event_pipeline_manager.pipelines:
                    event_pipe_manager.add_transporter(
                        (pipe.source.support_event,
                         self._get_notifiers(transport, pipe)))
            else:
                event_pipe_manager = self.event_pipeline_manager

            return event_pipe_manager

    def start(self):
        super(NotificationService, self).start()

        self.pipeline_manager = pipeline.setup_pipeline()
        self.transport = messaging.get_transport()

        if cfg.CONF.notification.workload_partitioning:
            self.ctxt = context.get_admin_context()
            self.group_id = self.NOTIFICATION_NAMESPACE
            self.partition_coordinator = coordination.PartitionCoordinator()
            self.partition_coordinator.start()
            self.partition_coordinator.join_group(self.group_id)
        else:
            # FIXME(sileht): endpoint use notification_topics option
            # and it should not because this is oslo_messaging option
            # not a ceilometer, until we have a something to get
            # the notification_topics in an other way
            # we must create a transport to ensure the option have
            # beeen registered by oslo_messaging
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
            self._configure_pipeline_listeners()
            self.partition_coordinator.watch_group(self.group_id,
                                                   self._refresh_agent)

            self.tg.add_timer(cfg.CONF.coordination.heartbeat,
                              self.partition_coordinator.heartbeat)
            self.tg.add_timer(cfg.CONF.coordination.check_watchers,
                              self.partition_coordinator.run_watchers)

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
            LOG.debug(_('Event types from %(name)s: %(type)s'
                        ' (ack_on_error=%(error)s)') %
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
            listener = messaging.get_notification_listener(
                transport, targets, endpoints)
            listener.start()
            self.listeners.append(listener)

    def _refresh_agent(self, event):
        self.reload_pipeline()

    def _refresh_listeners(self):
        utils.kill_listeners(self.pipeline_listeners)
        self._configure_pipeline_listeners()

    def _configure_pipeline_listeners(self):
        self.pipeline_listeners = []
        ev_pipes = []
        if cfg.CONF.notification.store_events:
            ev_pipes = self.event_pipeline_manager.pipelines
        pipelines = self.pipeline_manager.pipelines + ev_pipes
        transport = messaging.get_transport()
        for pipe in pipelines:
            LOG.debug(_('Pipeline endpoint: %s'), pipe.name)
            pipe_endpoint = (pipeline.EventPipelineEndpoint
                             if isinstance(pipe, pipeline.EventPipeline) else
                             pipeline.SamplePipelineEndpoint)
            listener = messaging.get_notification_listener(
                transport,
                [oslo_messaging.Target(
                    topic='%s-%s-%s' % (self.NOTIFICATION_IPC,
                                        pipe.name,
                                        self.partition_coordinator._my_id))],
                [pipe_endpoint(self.ctxt, pipe)])
            listener.start()
            self.pipeline_listeners.append(listener)

    def stop(self):
        if self.partition_coordinator:
            self.partition_coordinator.stop()
        utils.kill_listeners(self.listeners + self.pipeline_listeners)
        super(NotificationService, self).stop()

    def reload_pipeline(self):
        LOG.info(_LI("Reloading notification agent and listeners."))

        self.pipe_manager = self._get_pipe_manager(
            self.transport, self.pipeline_manager)

        self.event_pipe_manager = self._get_event_pipeline_manager(
            self.transport)

        # re-start the main queue listeners.
        utils.kill_listeners(self.listeners)
        self._configure_main_queue_listeners(
            self.pipe_manager, self.event_pipe_manager)

        # re-start the pipeline listeners if workload partitioning
        # is enabled.
        if cfg.CONF.notification.workload_partitioning:
            self._refresh_listeners()
