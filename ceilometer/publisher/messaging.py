#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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
"""Publish a sample using the preferred RPC mechanism.
"""

import abc
import itertools
import operator

from oslo_config import cfg
from oslo_log import log
import oslo_messaging
from oslo_utils import encodeutils
from oslo_utils import excutils
import six
import six.moves.urllib.parse as urlparse

from ceilometer.i18n import _, _LE, _LI
from ceilometer import messaging
from ceilometer import publisher
from ceilometer.publisher import utils


LOG = log.getLogger(__name__)

NOTIFIER_OPTS = [
    cfg.StrOpt('metering_topic',
               default='metering',
               help='The topic that ceilometer uses for metering '
               'notifications.',
               ),
    cfg.StrOpt('event_topic',
               default='event',
               help='The topic that ceilometer uses for event '
               'notifications.',
               ),
    cfg.StrOpt('telemetry_driver',
               default='messagingv2',
               help='The driver that ceilometer uses for metering '
               'notifications.',
               deprecated_name='metering_driver',
               )
]

cfg.CONF.register_opts(NOTIFIER_OPTS,
                       group="publisher_notifier")
cfg.CONF.import_opt('host', 'ceilometer.service')


class DeliveryFailure(Exception):
    def __init__(self, message=None, cause=None):
        super(DeliveryFailure, self).__init__(message)
        self.cause = cause


def raise_delivery_failure(exc):
    excutils.raise_with_cause(DeliveryFailure,
                              encodeutils.exception_to_unicode(exc),
                              cause=exc)


@six.add_metaclass(abc.ABCMeta)
class MessagingPublisher(publisher.PublisherBase):

    def __init__(self, parsed_url):
        options = urlparse.parse_qs(parsed_url.query)
        # the value of options is a list of url param values
        # only take care of the latest one if the option
        # is provided more than once
        self.per_meter_topic = bool(int(
            options.get('per_meter_topic', [0])[-1]))

        self.policy = options.get('policy', ['default'])[-1]
        self.max_queue_length = int(options.get(
            'max_queue_length', [1024])[-1])
        self.max_retry = 0

        self.local_queue = []

        if self.policy in ['default', 'queue', 'drop']:
            LOG.info(_LI('Publishing policy set to %s') % self.policy)
        else:
            LOG.warning(_('Publishing policy is unknown (%s) force to '
                          'default') % self.policy)
            self.policy = 'default'

        self.retry = 1 if self.policy in ['queue', 'drop'] else None

    def publish_samples(self, context, samples):
        """Publish samples on RPC.

        :param context: Execution context from the service or RPC call.
        :param samples: Samples from pipeline after transformation.

        """

        meters = [
            utils.meter_message_from_counter(
                sample, cfg.CONF.publisher.telemetry_secret)
            for sample in samples
        ]
        topic = cfg.CONF.publisher_notifier.metering_topic
        self.local_queue.append((context, topic, meters))

        if self.per_meter_topic:
            for meter_name, meter_list in itertools.groupby(
                    sorted(meters, key=operator.itemgetter('counter_name')),
                    operator.itemgetter('counter_name')):
                meter_list = list(meter_list)
                topic_name = topic + '.' + meter_name
                LOG.debug('Publishing %(m)d samples on %(n)s',
                          {'m': len(meter_list), 'n': topic_name})
                self.local_queue.append((context, topic_name, meter_list))

        self.flush()

    def flush(self):
        # NOTE(sileht):
        # this is why the self.local_queue is emptied before processing the
        # queue and the remaining messages in the queue are added to
        # self.local_queue after in case of another call having already added
        # something in the self.local_queue
        queue = self.local_queue
        self.local_queue = []
        self.local_queue = (self._process_queue(queue, self.policy) +
                            self.local_queue)
        if self.policy == 'queue':
            self._check_queue_length()

    def _check_queue_length(self):
        queue_length = len(self.local_queue)
        if queue_length > self.max_queue_length > 0:
            count = queue_length - self.max_queue_length
            self.local_queue = self.local_queue[count:]
            LOG.warning(_("Publisher max local_queue length is exceeded, "
                        "dropping %d oldest samples") % count)

    def _process_queue(self, queue, policy):
        current_retry = 0
        while queue:
            context, topic, data = queue[0]
            try:
                self._send(context, topic, data)
            except DeliveryFailure:
                data = sum([len(m) for __, __, m in queue])
                if policy == 'queue':
                    LOG.warning(_("Failed to publish %d datapoints, queue "
                                  "them"), data)
                    return queue
                elif policy == 'drop':
                    LOG.warning(_("Failed to publish %d datapoints, "
                                "dropping them"), data)
                    return []
                current_retry += 1
                if current_retry >= self.max_retry:
                    LOG.exception(_LE("Failed to retry to send sample data "
                                      "with max_retry times"))
                    raise
            else:
                queue.pop(0)
        return []

    def publish_events(self, context, events):
        """Send an event message for publishing

        :param context: Execution context from the service or RPC call
        :param events: events from pipeline after transformation
        """
        ev_list = [utils.message_from_event(
            event, cfg.CONF.publisher.telemetry_secret) for event in events]

        topic = cfg.CONF.publisher_notifier.event_topic
        self.local_queue.append((context, topic, ev_list))
        self.flush()

    @abc.abstractmethod
    def _send(self, context, topic, meters):
        """Send the meters to the messaging topic."""


class NotifierPublisher(MessagingPublisher):
    def __init__(self, parsed_url, default_topic):
        super(NotifierPublisher, self).__init__(parsed_url)
        options = urlparse.parse_qs(parsed_url.query)
        topic = options.get('topic', [default_topic])[-1]
        self.notifier = oslo_messaging.Notifier(
            messaging.get_transport(),
            driver=cfg.CONF.publisher_notifier.telemetry_driver,
            publisher_id='telemetry.publisher.%s' % cfg.CONF.host,
            topic=topic,
            retry=self.retry
        )

    def _send(self, context, event_type, data):
        try:
            self.notifier.sample(context.to_dict(), event_type=event_type,
                                 payload=data)
        except oslo_messaging.MessageDeliveryFailure as e:
            raise_delivery_failure(e)


class SampleNotifierPublisher(NotifierPublisher):
    def __init__(self, parsed_url):
        super(SampleNotifierPublisher, self).__init__(
            parsed_url, cfg.CONF.publisher_notifier.metering_topic)


class EventNotifierPublisher(NotifierPublisher):
    def __init__(self, parsed_url):
        super(EventNotifierPublisher, self).__init__(
            parsed_url, cfg.CONF.publisher_notifier.event_topic)
