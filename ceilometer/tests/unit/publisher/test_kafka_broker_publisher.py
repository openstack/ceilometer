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
"""Tests for ceilometer/publisher/kafka_broker.py
"""
import datetime
import uuid

import mock
from oslo_utils import netutils

from ceilometer.event.storage import models as event
from ceilometer.publisher import kafka_broker as kafka
from ceilometer.publisher import messaging as msg_publisher
from ceilometer import sample
from ceilometer import service
from ceilometer.tests import base as tests_base


@mock.patch('ceilometer.publisher.kafka_broker.LOG', mock.Mock())
class TestKafkaPublisher(tests_base.BaseTestCase):
    test_event_data = [
        event.Event(message_id=uuid.uuid4(),
                    event_type='event_%d' % i,
                    generated=datetime.datetime.utcnow(),
                    traits=[], raw={})
        for i in range(0, 5)
    ]

    test_data = [
        sample.Sample(
            name='test',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
        sample.Sample(
            name='test',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
        sample.Sample(
            name='test2',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
        sample.Sample(
            name='test2',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
        sample.Sample(
            name='test3',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
    ]

    def setUp(self):
        super(TestKafkaPublisher, self).setUp()
        self.CONF = service.prepare_service([], [])

    def test_publish(self):
        publisher = kafka.KafkaBrokerPublisher(self.CONF, netutils.urlsplit(
            'kafka://127.0.0.1:9092?topic=ceilometer'))

        with mock.patch.object(publisher, '_producer') as fake_producer:
            publisher.publish_samples(self.test_data)
            self.assertEqual(5, len(fake_producer.send.mock_calls))
            self.assertEqual(0, len(publisher.local_queue))

    def test_publish_without_options(self):
        publisher = kafka.KafkaBrokerPublisher(
            self.CONF, netutils.urlsplit('kafka://127.0.0.1:9092'))

        with mock.patch.object(publisher, '_producer') as fake_producer:
            publisher.publish_samples(self.test_data)
            self.assertEqual(5, len(fake_producer.send.mock_calls))
            self.assertEqual(0, len(publisher.local_queue))

    def test_publish_to_host_without_policy(self):
        publisher = kafka.KafkaBrokerPublisher(self.CONF, netutils.urlsplit(
            'kafka://127.0.0.1:9092?topic=ceilometer'))
        self.assertEqual('default', publisher.policy)

        publisher = kafka.KafkaBrokerPublisher(self.CONF, netutils.urlsplit(
            'kafka://127.0.0.1:9092?topic=ceilometer&policy=test'))
        self.assertEqual('default', publisher.policy)

    def test_publish_to_host_with_default_policy(self):
        publisher = kafka.KafkaBrokerPublisher(self.CONF, netutils.urlsplit(
            'kafka://127.0.0.1:9092?topic=ceilometer&policy=default'))

        with mock.patch.object(publisher, '_producer') as fake_producer:
            fake_producer.send.side_effect = TypeError
            self.assertRaises(msg_publisher.DeliveryFailure,
                              publisher.publish_samples,
                              self.test_data)
            self.assertEqual(100, len(fake_producer.send.mock_calls))
            self.assertEqual(0, len(publisher.local_queue))

    def test_publish_to_host_with_drop_policy(self):
        publisher = kafka.KafkaBrokerPublisher(self.CONF, netutils.urlsplit(
            'kafka://127.0.0.1:9092?topic=ceilometer&policy=drop'))

        with mock.patch.object(publisher, '_producer') as fake_producer:
            fake_producer.send.side_effect = Exception("test")
            publisher.publish_samples(self.test_data)
            self.assertEqual(1, len(fake_producer.send.mock_calls))
            self.assertEqual(0, len(publisher.local_queue))

    def test_publish_to_host_with_queue_policy(self):
        publisher = kafka.KafkaBrokerPublisher(self.CONF, netutils.urlsplit(
            'kafka://127.0.0.1:9092?topic=ceilometer&policy=queue'))

        with mock.patch.object(publisher, '_producer') as fake_producer:
            fake_producer.send.side_effect = Exception("test")
            publisher.publish_samples(self.test_data)
            self.assertEqual(1, len(fake_producer.send.mock_calls))
            self.assertEqual(1, len(publisher.local_queue))

    def test_publish_to_down_host_with_default_queue_size(self):
        publisher = kafka.KafkaBrokerPublisher(self.CONF, netutils.urlsplit(
            'kafka://127.0.0.1:9092?topic=ceilometer&policy=queue'))

        with mock.patch.object(publisher, '_producer') as fake_producer:
            fake_producer.send.side_effect = Exception("test")

            for i in range(0, 2000):
                for s in self.test_data:
                    s.name = 'test-%d' % i
                publisher.publish_samples(self.test_data)

            self.assertEqual(1024, len(publisher.local_queue))
            self.assertEqual('test-976',
                             publisher.local_queue[0][1][0]['counter_name'])
            self.assertEqual('test-1999',
                             publisher.local_queue[1023][1][0]['counter_name'])

    def test_publish_to_host_from_down_to_up_with_queue(self):
        publisher = kafka.KafkaBrokerPublisher(self.CONF, netutils.urlsplit(
            'kafka://127.0.0.1:9092?topic=ceilometer&policy=queue'))

        with mock.patch.object(publisher, '_producer') as fake_producer:
            fake_producer.send.side_effect = Exception("test")
            for i in range(0, 16):
                for s in self.test_data:
                    s.name = 'test-%d' % i
                publisher.publish_samples(self.test_data)

            self.assertEqual(16, len(publisher.local_queue))

            fake_producer.send.side_effect = None
            for s in self.test_data:
                s.name = 'test-%d' % 16
            publisher.publish_samples(self.test_data)
            self.assertEqual(0, len(publisher.local_queue))

    def test_publish_event_with_default_policy(self):
        publisher = kafka.KafkaBrokerPublisher(self.CONF, netutils.urlsplit(
            'kafka://127.0.0.1:9092?topic=ceilometer'))

        with mock.patch.object(publisher, '_producer') as fake_producer:
            publisher.publish_events(self.test_event_data)
            self.assertEqual(5, len(fake_producer.send.mock_calls))

        with mock.patch.object(publisher, '_producer') as fake_producer:
            fake_producer.send.side_effect = Exception("test")
            self.assertRaises(msg_publisher.DeliveryFailure,
                              publisher.publish_events,
                              self.test_event_data)
            self.assertEqual(100, len(fake_producer.send.mock_calls))
            self.assertEqual(0, len(publisher.local_queue))
