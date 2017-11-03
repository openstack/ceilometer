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
from itertools import chain

from oslo_log import log
import oslo_messaging
from oslo_utils import timeutils
from stevedore import extension

from ceilometer import agent
from ceilometer.event import converter
from ceilometer.event import models
from ceilometer.pipeline import base
from ceilometer.publisher import utils as publisher_utils

LOG = log.getLogger(__name__)


class EventEndpoint(base.MainNotificationEndpoint):

    event_types = []

    def __init__(self, conf, publisher):
        super(EventEndpoint, self).__init__(conf, publisher)
        LOG.debug('Loading event definitions')
        self.event_converter = converter.setup_events(
            conf,
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
                    with self.publisher as p:
                        p(event)
            except Exception:
                if not self.conf.notification.ack_on_event_error:
                    return oslo_messaging.NotificationResult.REQUEUE
                LOG.error('Fail to process a notification', exc_info=True)
        return oslo_messaging.NotificationResult.HANDLED


class InterimEventEndpoint(base.NotificationEndpoint):
    def __init__(self, conf, publisher, pipe_name):
        self.event_types = [pipe_name]
        super(InterimEventEndpoint, self).__init__(conf, publisher)

    def sample(self, notifications):
        return self.process_notifications('sample', notifications)

    def process_notifications(self, priority, notifications):
        events = chain.from_iterable(m["payload"] for m in notifications)
        events = [
            models.Event(
                message_id=ev['message_id'],
                event_type=ev['event_type'],
                generated=timeutils.normalize_time(
                    timeutils.parse_isotime(ev['generated'])),
                traits=[models.Trait(name, dtype,
                                     models.Trait.convert_value(dtype, value))
                        for name, dtype, value in ev['traits']],
                raw=ev.get('raw', {}))
            for ev in events if publisher_utils.verify_signature(
                ev, self.conf.publisher.telemetry_secret)
        ]
        try:
            with self.publisher as p:
                p(events)
        except Exception:
            if not self.conf.notification.ack_on_event_error:
                return oslo_messaging.NotificationResult.REQUEUE
            raise
        return oslo_messaging.NotificationResult.HANDLED


class EventSource(base.PipelineSource):
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
            raise base.PipelineException(err.msg, cfg)

    def support_event(self, event_name):
        return self.is_supported(self.events, event_name)


class EventSink(base.Sink):

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


class EventPipeline(base.Pipeline):
    """Represents a pipeline for Events."""

    default_grouping_key = ['event_type']

    def __str__(self):
        # NOTE(gordc): prepend a namespace so we ensure event and sample
        #              pipelines do not have the same name.
        return 'event:%s' % super(EventPipeline, self).__str__()

    def publish_data(self, events):
        if not isinstance(events, list):
            events = [events]
        supported = [e for e in events if self.supported(e)]
        self.sink.publish_events(supported)

    def serializer(self, event):
        return publisher_utils.message_from_event(
            event, self.conf.publisher.telemetry_secret)

    def supported(self, event):
        return self.source.support_event(event.event_type)


class EventPipelineManager(base.PipelineManager):

    pm_type = 'event'
    pm_pipeline = EventPipeline
    pm_source = EventSource
    pm_sink = EventSink

    def __init__(self, conf, partition=False):
        super(EventPipelineManager, self).__init__(
            conf, conf.event_pipeline_cfg_file, {}, partition)

    def get_main_endpoints(self):
        return [EventEndpoint(self.conf, self.get_main_publisher())]

    def get_interim_endpoints(self):
        # FIXME(gordc): change this so we shard data rather than per
        # pipeline. this will allow us to use self.publisher and less
        # queues.
        return [InterimEventEndpoint(
            self.conf, base.PublishContext([pipe]), pipe.name)
            for pipe in self.pipelines]
