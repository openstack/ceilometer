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
import threading

from oslo_config import cfg
from oslo_log import log
import oslo_messaging
from oslo_utils import encodeutils
from oslo_utils import excutils
import six
import six.moves.urllib.parse as urlparse

from ceilometer.i18n import _
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


class DeliveryFailure(Exception):
    def __init__(self, message=None, cause=None):
        super(DeliveryFailure, self).__init__(message)
        self.cause = cause


def raise_delivery_failure(exc):
    excutils.raise_with_cause(DeliveryFailure,
                              encodeutils.exception_to_unicode(exc),
                              cause=exc)


@six.add_metaclass(abc.ABCMeta)
class MessagingPublisher(publisher.ConfigPublisherBase):

    def __init__(self, conf, parsed_url):
        super(MessagingPublisher, self).__init__(conf, parsed_url)
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

        self.queue_lock = threading.Lock()
        self.local_queue = []

        if self.policy in ['default', 'queue', 'drop']:
            LOG.info('Publishing policy set to %s', self.policy)
        else:
            LOG.warning(_('Publishing policy is unknown (%s) force to '
                          'default'), self.policy)
            self.policy = 'default'

        self.retry = 1 if self.policy in ['queue', 'drop'] else None

    def publish_samples(self, samples):
        """Publish samples on RPC.

        :param samples: Samples from pipeline after transformation.

        """

        meters = [
            utils.meter_message_from_counter(
                sample, self.conf.publisher.telemetry_secret)
            for sample in samples
        ]
        topic = self.conf.publisher_notifier.metering_topic
        self.local_queue.append((topic, meters))

        if self.per_meter_topic:
            for meter_name, meter_list in itertools.groupby(
                    sorted(meters, key=operator.itemgetter('counter_name')),
                    operator.itemgetter('counter_name')):
                meter_list = list(meter_list)
                topic_name = topic + '.' + meter_name
                LOG.debug('Publishing %(m)d samples on %(n)s',
                          {'m': len(meter_list), 'n': topic_name})
                self.local_queue.append((topic_name, meter_list))

        self.flush()

    def flush(self):
        with self.queue_lock:
            queue = self.local_queue
            self.local_queue = []

        queue = self._process_queue(queue, self.policy)

        with self.queue_lock:
            self.local_queue = (queue + self.local_queue)
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
            topic, data = queue[0]
            try:
                self._send(topic, data)
            except DeliveryFailure:
                data = sum([len(m) for __, m in queue])
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
                    LOG.exception("Failed to retry to send sample data "
                                  "with max_retry times")
                    raise
            else:
                queue.pop(0)
        return []

    def publish_events(self, events):
        """Send an event message for publishing

        :param events: events from pipeline after transformation
        """
        ev_list = [utils.message_from_event(
            event, self.conf.publisher.telemetry_secret) for event in events]

        topic = self.conf.publisher_notifier.event_topic
        self.local_queue.append((topic, ev_list))
        self.flush()

    @abc.abstractmethod
    def _send(self, topic, meters):
        """Send the meters to the messaging topic."""


class NotifierPublisher(MessagingPublisher):
    """Publish metering data from notifer publisher.

    The ip address and port number of notifer can be configured in
    ceilometer pipeline configuration file.

    User can customize the transport driver such as rabbit, kafka and
    so on. The Notifer uses `sample` method as default method to send
    notifications.

    This publisher has transmit options such as queue, drop, and
    retry. These options are specified using policy field of URL parameter.
    When queue option could be selected, local queue length can be determined
    using max_queue_length field as well. When the transfer fails with retry
    option, try to resend the data as many times as specified in max_retry
    field. If max_retry is not specified, by default the number of retry
    is 100.

    To enable this publisher, add the following section to the
    /etc/ceilometer/pipeline.yaml file or simply add it to an existing
    pipeline::

        meter:
            - name: meter_notifier
              meters:
                - "*"
              sinks:
                - notifier_sink
        sinks:
            - name: notifier_sink
              transformers:
              publishers:
                - notifer://[notifier_ip]:[notifier_port]?topic=[topic]&
                  driver=driver&max_retry=100

    """

    def __init__(self, conf, parsed_url, default_topic):
        super(NotifierPublisher, self).__init__(conf, parsed_url)
        options = urlparse.parse_qs(parsed_url.query)
        topics = options.pop('topic', [default_topic])
        driver = options.pop('driver', ['rabbit'])[0]
        self.max_retry = int(options.get('max_retry', [100])[-1])

        url = None
        if parsed_url.netloc != '':
            url = urlparse.urlunsplit([driver, parsed_url.netloc,
                                       parsed_url.path,
                                       urlparse.urlencode(options, True),
                                       parsed_url.fragment])
        self.notifier = oslo_messaging.Notifier(
            messaging.get_transport(self.conf, url),
            driver=self.conf.publisher_notifier.telemetry_driver,
            publisher_id='telemetry.publisher.%s' % self.conf.host,
            topics=topics,
            retry=self.retry
        )

    def _send(self, event_type, data):
        try:
            self.notifier.sample({}, event_type=event_type,
                                 payload=data)
        except oslo_messaging.MessageDeliveryFailure as e:
            raise_delivery_failure(e)


class SampleNotifierPublisher(NotifierPublisher):
    def __init__(self, conf, parsed_url):
        super(SampleNotifierPublisher, self).__init__(
            conf, parsed_url, conf.publisher_notifier.metering_topic)


class EventNotifierPublisher(NotifierPublisher):
    def __init__(self, conf, parsed_url):
        super(EventNotifierPublisher, self).__init__(
            conf, parsed_url, conf.publisher_notifier.event_topic)
