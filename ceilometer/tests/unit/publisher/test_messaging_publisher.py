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
"""Tests for ceilometer/publisher/messaging.py
"""
import datetime
import uuid

import mock
import oslo_messaging
from oslo_messaging._drivers import impl_kafka as kafka_driver
from oslo_utils import netutils
import testscenarios.testcase

from ceilometer.event.storage import models as event
from ceilometer.publisher import messaging as msg_publisher
from ceilometer import sample
from ceilometer import service
from ceilometer.tests import base as tests_base


class BasePublisherTestCase(tests_base.BaseTestCase):
    test_event_data = [
        event.Event(message_id=uuid.uuid4(),
                    event_type='event_%d' % i,
                    generated=datetime.datetime.utcnow(),
                    traits=[], raw={})
        for i in range(0, 5)
    ]

    test_sample_data = [
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
        super(BasePublisherTestCase, self).setUp()
        self.CONF = service.prepare_service([], [])
        self.setup_messaging(self.CONF)


class NotifierOnlyPublisherTest(BasePublisherTestCase):

    @mock.patch('oslo_messaging.Notifier')
    def test_publish_topic_override(self, notifier):
        msg_publisher.SampleNotifierPublisher(
            self.CONF,
            netutils.urlsplit('notifier://?topic=custom_topic'))
        notifier.assert_called_with(mock.ANY, topics=['custom_topic'],
                                    driver=mock.ANY, retry=mock.ANY,
                                    publisher_id=mock.ANY)

        msg_publisher.EventNotifierPublisher(
            self.CONF,
            netutils.urlsplit('notifier://?topic=custom_event_topic'))
        notifier.assert_called_with(mock.ANY, topics=['custom_event_topic'],
                                    driver=mock.ANY, retry=mock.ANY,
                                    publisher_id=mock.ANY)

    @mock.patch('ceilometer.messaging.get_transport')
    def test_publish_other_host(self, cgt):
        msg_publisher.SampleNotifierPublisher(
            self.CONF,
            netutils.urlsplit('notifier://foo:foo@127.0.0.1:1234'))
        cgt.assert_called_with(self.CONF, 'rabbit://foo:foo@127.0.0.1:1234')

        msg_publisher.EventNotifierPublisher(
            self.CONF,
            netutils.urlsplit('notifier://foo:foo@127.0.0.1:1234'))
        cgt.assert_called_with(self.CONF, 'rabbit://foo:foo@127.0.0.1:1234')

    @mock.patch('ceilometer.messaging.get_transport')
    def test_publish_other_host_vhost_and_query(self, cgt):
        msg_publisher.SampleNotifierPublisher(
            self.CONF,
            netutils.urlsplit('notifier://foo:foo@127.0.0.1:1234/foo'
                              '?driver=amqp&amqp_auto_delete=true'))
        cgt.assert_called_with(self.CONF, 'amqp://foo:foo@127.0.0.1:1234/foo'
                               '?amqp_auto_delete=true')

        msg_publisher.EventNotifierPublisher(
            self.CONF,
            netutils.urlsplit('notifier://foo:foo@127.0.0.1:1234/foo'
                              '?driver=amqp&amqp_auto_delete=true'))
        cgt.assert_called_with(self.CONF, 'amqp://foo:foo@127.0.0.1:1234/foo'
                               '?amqp_auto_delete=true')

    @mock.patch('ceilometer.messaging.get_transport')
    def test_publish_with_none_rabbit_driver(self, cgt):
        sample_publisher = msg_publisher.SampleNotifierPublisher(
            self.CONF,
            netutils.urlsplit('notifier://127.0.0.1:9092?driver=kafka'))
        cgt.assert_called_with(self.CONF, 'kafka://127.0.0.1:9092')
        transport = oslo_messaging.get_transport(self.CONF,
                                                 'kafka://127.0.0.1:9092')
        self.assertIsInstance(transport._driver, kafka_driver.KafkaDriver)

        side_effect = msg_publisher.DeliveryFailure()
        with mock.patch.object(sample_publisher, '_send') as fake_send:
            fake_send.side_effect = side_effect
            self.assertRaises(
                msg_publisher.DeliveryFailure,
                sample_publisher.publish_samples,
                self.test_sample_data)
            self.assertEqual(0, len(sample_publisher.local_queue))
            self.assertEqual(100, len(fake_send.mock_calls))
            fake_send.assert_called_with('metering', mock.ANY)

        event_publisher = msg_publisher.EventNotifierPublisher(
            self.CONF,
            netutils.urlsplit('notifier://127.0.0.1:9092?driver=kafka'))
        cgt.assert_called_with(self.CONF, 'kafka://127.0.0.1:9092')

        with mock.patch.object(event_publisher, '_send') as fake_send:
            fake_send.side_effect = side_effect
            self.assertRaises(
                msg_publisher.DeliveryFailure,
                event_publisher.publish_events,
                self.test_event_data)
            self.assertEqual(0, len(event_publisher.local_queue))
            self.assertEqual(100, len(fake_send.mock_calls))
            fake_send.assert_called_with('event', mock.ANY)


class TestPublisher(testscenarios.testcase.WithScenarios,
                    BasePublisherTestCase):
    scenarios = [
        ('notifier',
         dict(protocol="notifier",
              publisher_cls=msg_publisher.SampleNotifierPublisher,
              test_data=BasePublisherTestCase.test_sample_data,
              pub_func='publish_samples', attr='source')),
        ('event_notifier',
         dict(protocol="notifier",
              publisher_cls=msg_publisher.EventNotifierPublisher,
              test_data=BasePublisherTestCase.test_event_data,
              pub_func='publish_events', attr='event_type')),
    ]

    def setUp(self):
        super(TestPublisher, self).setUp()
        self.topic = (self.CONF.publisher_notifier.event_topic
                      if self.pub_func == 'publish_events' else
                      self.CONF.publisher_notifier.metering_topic)


class TestPublisherPolicy(TestPublisher):
    @mock.patch('ceilometer.publisher.messaging.LOG')
    def test_published_with_no_policy(self, mylog):
        publisher = self.publisher_cls(
            self.CONF,
            netutils.urlsplit('%s://' % self.protocol))
        side_effect = msg_publisher.DeliveryFailure()
        with mock.patch.object(publisher, '_send') as fake_send:
            fake_send.side_effect = side_effect
            self.assertRaises(
                msg_publisher.DeliveryFailure,
                getattr(publisher, self.pub_func),
                self.test_data)
            self.assertTrue(mylog.info.called)
            self.assertEqual('default', publisher.policy)
            self.assertEqual(0, len(publisher.local_queue))
            self.assertEqual(100, len(fake_send.mock_calls))
            fake_send.assert_called_with(
                self.topic, mock.ANY)

    @mock.patch('ceilometer.publisher.messaging.LOG')
    def test_published_with_policy_block(self, mylog):
        publisher = self.publisher_cls(
            self.CONF,
            netutils.urlsplit('%s://?policy=default' % self.protocol))
        side_effect = msg_publisher.DeliveryFailure()
        with mock.patch.object(publisher, '_send') as fake_send:
            fake_send.side_effect = side_effect
            self.assertRaises(
                msg_publisher.DeliveryFailure,
                getattr(publisher, self.pub_func),
                self.test_data)
            self.assertTrue(mylog.info.called)
            self.assertEqual(0, len(publisher.local_queue))
            self.assertEqual(100, len(fake_send.mock_calls))
            fake_send.assert_called_with(
                self.topic, mock.ANY)

    @mock.patch('ceilometer.publisher.messaging.LOG')
    def test_published_with_policy_incorrect(self, mylog):
        publisher = self.publisher_cls(
            self.CONF,
            netutils.urlsplit('%s://?policy=notexist' % self.protocol))
        side_effect = msg_publisher.DeliveryFailure()
        with mock.patch.object(publisher, '_send') as fake_send:
            fake_send.side_effect = side_effect
            self.assertRaises(
                msg_publisher.DeliveryFailure,
                getattr(publisher, self.pub_func),
                self.test_data)
            self.assertTrue(mylog.warning.called)
            self.assertEqual('default', publisher.policy)
            self.assertEqual(0, len(publisher.local_queue))
            self.assertEqual(100, len(fake_send.mock_calls))
            fake_send.assert_called_with(
                self.topic, mock.ANY)


@mock.patch('ceilometer.publisher.messaging.LOG', mock.Mock())
class TestPublisherPolicyReactions(TestPublisher):

    def test_published_with_policy_drop_and_rpc_down(self):
        publisher = self.publisher_cls(
            self.CONF,
            netutils.urlsplit('%s://?policy=drop' % self.protocol))
        side_effect = msg_publisher.DeliveryFailure()
        with mock.patch.object(publisher, '_send') as fake_send:
            fake_send.side_effect = side_effect
            getattr(publisher, self.pub_func)(self.test_data)
            self.assertEqual(0, len(publisher.local_queue))
            fake_send.assert_called_once_with(
                self.topic, mock.ANY)

    def test_published_with_policy_queue_and_rpc_down(self):
        publisher = self.publisher_cls(
            self.CONF,
            netutils.urlsplit('%s://?policy=queue' % self.protocol))
        side_effect = msg_publisher.DeliveryFailure()
        with mock.patch.object(publisher, '_send') as fake_send:
            fake_send.side_effect = side_effect

            getattr(publisher, self.pub_func)(self.test_data)
            self.assertEqual(1, len(publisher.local_queue))
            fake_send.assert_called_once_with(
                self.topic, mock.ANY)

    def test_published_with_policy_queue_and_rpc_down_up(self):
        self.rpc_unreachable = True
        publisher = self.publisher_cls(
            self.CONF,
            netutils.urlsplit('%s://?policy=queue' % self.protocol))

        side_effect = msg_publisher.DeliveryFailure()
        with mock.patch.object(publisher, '_send') as fake_send:
            fake_send.side_effect = side_effect
            getattr(publisher, self.pub_func)(self.test_data)

            self.assertEqual(1, len(publisher.local_queue))

            fake_send.side_effect = mock.MagicMock()
            getattr(publisher, self.pub_func)(self.test_data)

            self.assertEqual(0, len(publisher.local_queue))

            topic = self.topic
            expected = [mock.call(topic, mock.ANY),
                        mock.call(topic, mock.ANY),
                        mock.call(topic, mock.ANY)]
            self.assertEqual(expected, fake_send.mock_calls)

    def test_published_with_policy_sized_queue_and_rpc_down(self):
        publisher = self.publisher_cls(self.CONF, netutils.urlsplit(
            '%s://?policy=queue&max_queue_length=3' % self.protocol))

        side_effect = msg_publisher.DeliveryFailure()
        with mock.patch.object(publisher, '_send') as fake_send:
            fake_send.side_effect = side_effect
            for i in range(0, 5):
                for s in self.test_data:
                    setattr(s, self.attr, 'test-%d' % i)
                getattr(publisher, self.pub_func)(self.test_data)

        self.assertEqual(3, len(publisher.local_queue))
        self.assertEqual(
            'test-2',
            publisher.local_queue[0][1][0][self.attr]
        )
        self.assertEqual(
            'test-3',
            publisher.local_queue[1][1][0][self.attr]
        )
        self.assertEqual(
            'test-4',
            publisher.local_queue[2][1][0][self.attr]
        )

    def test_published_with_policy_default_sized_queue_and_rpc_down(self):
        publisher = self.publisher_cls(
            self.CONF,
            netutils.urlsplit('%s://?policy=queue' % self.protocol))

        side_effect = msg_publisher.DeliveryFailure()
        with mock.patch.object(publisher, '_send') as fake_send:
            fake_send.side_effect = side_effect
            for i in range(0, 2000):
                for s in self.test_data:
                    setattr(s, self.attr, 'test-%d' % i)
                getattr(publisher, self.pub_func)(self.test_data)

        self.assertEqual(1024, len(publisher.local_queue))
        self.assertEqual(
            'test-976',
            publisher.local_queue[0][1][0][self.attr]
        )
        self.assertEqual(
            'test-1999',
            publisher.local_queue[1023][1][0][self.attr]
        )
