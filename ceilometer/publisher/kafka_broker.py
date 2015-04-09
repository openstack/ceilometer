#
# Copyright 2015 Cisco Inc.
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

import json

import kafka
from oslo_config import cfg
from oslo_utils import netutils
from six.moves.urllib import parse as urlparse

from ceilometer.i18n import _LE
from ceilometer.i18n import _LI
from ceilometer.i18n import _LW
from ceilometer.openstack.common import log
from ceilometer import publisher
from ceilometer.publisher import utils

LOG = log.getLogger(__name__)


class KafkaBrokerPublisher(publisher.PublisherBase):
    """Publish metering data to kafka broker.

    The ip address and port number of kafka broker should be configured in
    ceilometer pipeline configuration file. If an ip address is not specified,
    this kafka publisher will not publish any meters.

    To enable this publisher, add the following section to the
    /etc/ceilometer/pipeline.yaml file or simply add it to an existing
    pipeline::

        meter:
            - name: meter_kafka
            interval: 600
            counters:
                - "*"
            transformers:
            sinks:
                - kafka_sink
        sinks:
            - name: kafka_sink
            transformers:
            publishers:
                - kafka://[kafka_broker_ip]:[kafka_broker_port]?topic=[topic]

    Kafka topic name and broker's port are required for this publisher to work
    properly. If topic parameter is missing, this kafka publisher publish
    metering data under a topic name, 'ceilometer'. If the port number is not
    specified, this Kafka Publisher will use 9092 as the broker's port.
    This publisher has transmit options such as queue, drop, and retry. These
    this option is specified using policy field of URL parameter. When queue
    option could be selected, local queue length can be determined using
    max_queue_length field as well. When the transfer fails with with retry
    option, try to resend the data as many times as specified in max_retry
    field. If max_retry is not specified, default the number of retry is 100.
    """

    def __init__(self, parsed_url):
        self.kafka_client = None

        self.host, self.port = netutils.parse_host_port(
            parsed_url.netloc, default_port=9092)

        self.local_queue = []

        params = urlparse.parse_qs(parsed_url.query)
        self.topic = params.get('topic', ['ceilometer'])[-1]
        self.policy = params.get('policy', ['default'])[-1]
        self.max_queue_length = int(params.get(
            'max_queue_length', [1024])[-1])
        self.max_retry = int(params.get('max_retry', [100])[-1])

        if self.policy in ['default', 'drop', 'queue']:
            LOG.info(_LI('Publishing policy set to %s') % self.policy)
        else:
            LOG.warn(_LW('Publishing policy is unknown (%s) force to default')
                     % self.policy)
            self.policy = 'default'

        try:
            self._get_client()
        except Exception as e:
            LOG.exception(_LE("Failed to connect to Kafka service: %s"), e)

    def publish_samples(self, context, samples):
        """Send a metering message for kafka broker.

        :param context: Execution context from the service or RPC call
        :param samples: Samples from pipeline after transformation
        """
        samples_list = [
            utils.meter_message_from_counter(
                sample, cfg.CONF.publisher.telemetry_secret)
            for sample in samples
        ]

        self.local_queue.append(samples_list)

        try:
            self._check_kafka_connection()
        except Exception as e:
            raise e

        self.flush()

    def flush(self):
        queue = self.local_queue
        self.local_queue = self._process_queue(queue)
        if self.policy == 'queue':
            self._check_queue_length()

    def publish_events(self, context, events):
        """Send an event message for kafka broker.

        :param context: Execution context from the service or RPC call
        :param events: events from pipeline after transformation
        """
        events_list = [utils.message_from_event(
            event, cfg.CONF.publisher.telemetry_secret) for event in events]

        self.local_queue.append(events_list)

        try:
            self._check_kafka_connection()
        except Exception as e:
            raise e

        self.flush()

    def _process_queue(self, queue):
        current_retry = 0
        while queue:
            data = queue[0]
            try:
                self._send(data)
            except Exception:
                LOG.warn(_LW("Failed to publish %d datum"),
                         sum([len(d) for d in queue]))
                if self.policy == 'queue':
                    return queue
                elif self.policy == 'drop':
                    return []
                current_retry += 1
                if current_retry >= self.max_retry:
                    self.local_queue = []
                    LOG.exception(_LE("Failed to retry to send sample data "
                                      "with max_retry times"))
                    raise
            else:
                queue.pop(0)
        return []

    def _check_queue_length(self):
        queue_length = len(self.local_queue)
        if queue_length > self.max_queue_length > 0:
            diff = queue_length - self.max_queue_length
            self.local_queue = self.local_queue[diff:]
            LOG.warn(_LW("Kafka Publisher max local queue length is exceeded, "
                     "dropping %d oldest data") % diff)

    def _check_kafka_connection(self):
        try:
            self._get_client()
        except Exception as e:
            LOG.exception(_LE("Failed to connect to Kafka service: %s"), e)

            if self.policy == 'queue':
                self._check_queue_length()
            else:
                self.local_queue = []
            raise Exception('Kafka Client is not available, '
                            'please restart Kafka client')

    def _get_client(self):
        if not self.kafka_client:
            self.kafka_client = kafka.KafkaClient(
                "%s:%s" % (self.host, self.port))
            self.kafka_producer = kafka.SimpleProducer(self.kafka_client)

    def _send(self, data):
        for d in data:
            try:
                self.kafka_producer.send_messages(
                    self.topic, json.dumps(d))
            except Exception as e:
                LOG.exception(_LE("Failed to send sample data: %s"), e)
                raise
