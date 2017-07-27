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

from debtcollector import removals
import kafka
from oslo_log import log
from oslo_serialization import jsonutils
from oslo_utils import netutils
from six.moves.urllib import parse as urlparse

from ceilometer.publisher import messaging

LOG = log.getLogger(__name__)


@removals.removed_class("KafkaBrokerPublisher",
                        message="use NotifierPublisher instead",
                        removal_version='10.0')
class KafkaBrokerPublisher(messaging.MessagingPublisher):
    """Publish metering data to kafka broker.

    The ip address and port number of kafka broker should be configured in
    ceilometer pipeline configuration file. If an ip address is not specified,
    this kafka publisher will not publish any meters.

    To enable this publisher, add the following section to the
    /etc/ceilometer/pipeline.yaml file or simply add it to an existing
    pipeline::

        meter:
            - name: meter_kafka
            meters:
                - "*"
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
    options are specified using policy field of URL parameter. When queue
    option could be selected, local queue length can be determined using
    max_queue_length field as well. When the transfer fails with retry
    option, try to resend the data as many times as specified in max_retry
    field. If max_retry is not specified, default the number of retry is 100.
    """

    def __init__(self, conf, parsed_url):
        super(KafkaBrokerPublisher, self).__init__(conf, parsed_url)
        options = urlparse.parse_qs(parsed_url.query)

        self._producer = None
        self._host, self._port = netutils.parse_host_port(
            parsed_url.netloc, default_port=9092)
        self._topic = options.get('topic', ['ceilometer'])[-1]
        self.max_retry = int(options.get('max_retry', [100])[-1])

    def _ensure_connection(self):
        if self._producer:
            return

        try:
            self._producer = kafka.KafkaProducer(
                bootstrap_servers=["%s:%s" % (self._host, self._port)])
        except kafka.errors.KafkaError as e:
            LOG.exception("Failed to connect to Kafka service: %s", e)
            raise messaging.DeliveryFailure('Kafka Client is not available, '
                                            'please restart Kafka client')
        except Exception as e:
            LOG.exception("Failed to connect to Kafka service: %s", e)
            raise messaging.DeliveryFailure('Kafka Client is not available, '
                                            'please restart Kafka client')

    def _send(self, event_type, data):
        self._ensure_connection()
        # TODO(sileht): don't split the payload into multiple network
        # message ... but how to do that without breaking consuming
        # application...
        try:
            for d in data:
                self._producer.send(self._topic, jsonutils.dumps(d))
        except Exception as e:
            messaging.raise_delivery_failure(e)
