# Copyright 2012-2014 eNovance <licensing@enovance.com>
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

from oslo_log import log
import oslo_messaging
from stevedore import extension

from ceilometer import agent
from ceilometer.event import converter
from ceilometer import pipeline

LOG = log.getLogger(__name__)


class EventEndpoint(pipeline.NotificationEndpoint):

    event_types = []

    def __init__(self, manager):
        super(EventEndpoint, self).__init__(manager)
        LOG.debug('Loading event definitions')
        self.event_converter = converter.setup_events(
            manager.conf,
            extension.ExtensionManager(
                namespace='ceilometer.event.trait_plugin'))

    def info(self, notifications):
        """Convert message at info level to Ceilometer Event.

        :param notifications: list of notifications
        """
        return self.process_notifications('info', notifications)

    def error(self, notifications):
        """Convert message at error level to Ceilometer Event.

        :param notifications: list of notifications
        """
        return self.process_notifications('error', notifications)

    def process_notifications(self, priority, notifications):
        for message in notifications:
            try:
                event = self.event_converter.to_event(priority, message)
                if event is not None:
                    with self.manager.publisher() as p:
                        p(event)
            except Exception:
                if not self.manager.conf.notification.ack_on_event_error:
                    return oslo_messaging.NotificationResult.REQUEUE
                LOG.error('Fail to process a notification', exc_info=True)
        return oslo_messaging.NotificationResult.HANDLED


class EventSource(pipeline.PipelineSource):
    """Represents a source of events.

    In effect it is a set of notification handlers capturing events for a set
    of matching notifications.
    """

    def __init__(self, cfg):
        super(EventSource, self).__init__(cfg)
        self.events = cfg.get('events')
        try:
            self.check_source_filtering(self.events, 'events')
        except agent.SourceException as err:
            raise pipeline.PipelineException(err.msg, cfg)

    def support_event(self, event_name):
        return self.is_supported(self.events, event_name)


class EventSink(pipeline.Sink):

    def publish_events(self, events):
        if events:
            for p in self.publishers:
                try:
                    p.publish_events(events)
                except Exception:
                    LOG.error("Pipeline %(pipeline)s: %(status)s "
                              "after error from publisher %(pub)s" %
                              {'pipeline': self,
                               'status': 'Continue' if
                               self.multi_publish else 'Exit', 'pub': p},
                              exc_info=True)
                    if not self.multi_publish:
                        raise


class EventPipeline(pipeline.Pipeline):
    """Represents a pipeline for Events."""

    def __str__(self):
        # NOTE(gordc): prepend a namespace so we ensure event and sample
        #              pipelines do not have the same name.
        return 'event:%s' % super(EventPipeline, self).__str__()

    def support_event(self, event_type):
        return self.source.support_event(event_type)

    def publish_data(self, events):
        if not isinstance(events, list):
            events = [events]
        supported = [e for e in events
                     if self.source.support_event(e.event_type)]
        self.sink.publish_events(supported)


class EventPipelineManager(pipeline.PipelineManager):

    def __init__(self, conf, cfg_file, transformer_manager):
        # FIXME(gordc): improve how we set pipeline specific models
        pipeline_types = {'name': 'event', 'pipeline': EventPipeline,
                          'source': EventSource, 'sink': EventSink}
        super(EventPipelineManager, self).__init__(
            conf, cfg_file, transformer_manager, pipeline_types)


def setup_pipeline(conf, transformer_manager=None):
    """Setup event pipeline manager according to yaml config file."""
    default = extension.ExtensionManager('ceilometer.transformer')
    cfg_file = conf.event_pipeline_cfg_file
    return EventPipelineManager(
        conf, cfg_file, transformer_manager or default)
