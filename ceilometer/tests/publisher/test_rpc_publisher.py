#
# Copyright 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
#         Julien Danjou <julien@danjou.info>
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
"""Tests for ceilometer/publisher/rpc.py
"""
import datetime

import eventlet
import mock
import oslo.messaging
import oslo.messaging._drivers.common

from ceilometer import messaging
from ceilometer.openstack.common import context
from ceilometer.openstack.common.fixture import config
from ceilometer.openstack.common import network_utils
from ceilometer.publisher import rpc
from ceilometer import sample
from ceilometer.tests import base as tests_base


class TestPublish(tests_base.BaseTestCase):
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
        super(TestPublish, self).setUp()
        self.CONF = self.useFixture(config.Config()).conf
        self.setup_messaging(self.CONF)
        self.published = []

    def test_published_no_mock(self):
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://'))

        endpoint = mock.MagicMock(['record_metering_data'])
        collector = messaging.get_rpc_server(
            self.transport, self.CONF.publisher_rpc.metering_topic, endpoint)
        endpoint.record_metering_data.side_effect = \
            lambda *args, **kwds: collector.stop()

        collector.start()
        eventlet.sleep()
        publisher.publish_samples(context.RequestContext(),
                                  self.test_data)
        collector.wait()

        class Matcher(object):
            @staticmethod
            def __eq__(data):
                for i, sample_item in enumerate(data):
                    if sample_item['counter_name'] != self.test_data[i].name:
                        return False
                return True

        endpoint.record_metering_data.assert_called_once_with(
            mock.ANY, data=Matcher())

    def test_publish_target(self):
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://?target=custom_procedure_call'))
        cast_context = mock.MagicMock()
        with mock.patch.object(publisher.rpc_client, 'prepare') as prepare:
            prepare.return_value = cast_context
            publisher.publish_samples(mock.MagicMock(),
                                      self.test_data)

        prepare.assert_called_once_with(
            topic=self.CONF.publisher_rpc.metering_topic)
        cast_context.cast.assert_called_once_with(
            mock.ANY, 'custom_procedure_call', data=mock.ANY)

    def test_published_with_per_meter_topic(self):
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://?per_meter_topic=1'))
        with mock.patch.object(publisher.rpc_client, 'prepare') as prepare:
            publisher.publish_samples(mock.MagicMock(),
                                      self.test_data)

            class MeterGroupMatcher(object):
                def __eq__(self, meters):
                    return len(set(meter['counter_name']
                                   for meter in meters)) == 1

            topic = self.CONF.publisher_rpc.metering_topic
            expected = [mock.call(topic=topic),
                        mock.call().cast(mock.ANY, 'record_metering_data',
                                         data=mock.ANY),
                        mock.call(topic=topic + '.test'),
                        mock.call().cast(mock.ANY, 'record_metering_data',
                                         data=MeterGroupMatcher()),
                        mock.call(topic=topic + '.test2'),
                        mock.call().cast(mock.ANY, 'record_metering_data',
                                         data=MeterGroupMatcher()),
                        mock.call(topic=topic + '.test3'),
                        mock.call().cast(mock.ANY, 'record_metering_data',
                                         data=MeterGroupMatcher())]
            self.assertEqual(expected, prepare.mock_calls)

    def test_published_concurrency(self):
        """This test the concurrent access to the local queue
        of the rpc publisher
        """

        publisher = rpc.RPCPublisher(network_utils.urlsplit('rpc://'))
        cast_context = mock.MagicMock()

        with mock.patch.object(publisher.rpc_client, 'prepare') as prepare:
            def fake_prepare_go(topic):
                return cast_context

            def fake_prepare_wait(topic):
                prepare.side_effect = fake_prepare_go
                # Sleep to simulate concurrency and allow other threads to work
                eventlet.sleep(0)
                return cast_context

            prepare.side_effect = fake_prepare_wait

            job1 = eventlet.spawn(publisher.publish_samples,
                                  mock.MagicMock(), self.test_data)
            job2 = eventlet.spawn(publisher.publish_samples,
                                  mock.MagicMock(), self.test_data)

            job1.wait()
            job2.wait()

        self.assertEqual('default', publisher.policy)
        self.assertEqual(2, len(cast_context.cast.mock_calls))
        self.assertEqual(0, len(publisher.local_queue))

    @mock.patch('ceilometer.publisher.rpc.LOG')
    def test_published_with_no_policy(self, mylog):
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://'))
        side_effect = oslo.messaging._drivers.common.RPCException()
        with mock.patch.object(publisher.rpc_client, 'prepare') as prepare:
            prepare.side_effect = side_effect

            self.assertRaises(
                oslo.messaging._drivers.common.RPCException,
                publisher.publish_samples,
                mock.MagicMock(), self.test_data)
            self.assertTrue(mylog.info.called)
            self.assertEqual('default', publisher.policy)
            self.assertEqual(0, len(publisher.local_queue))
            prepare.assert_called_once_with(
                topic=self.CONF.publisher_rpc.metering_topic)

    @mock.patch('ceilometer.publisher.rpc.LOG')
    def test_published_with_policy_block(self, mylog):
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://?policy=default'))
        side_effect = oslo.messaging._drivers.common.RPCException()
        with mock.patch.object(publisher.rpc_client, 'prepare') as prepare:
            prepare.side_effect = side_effect
            self.assertRaises(
                oslo.messaging._drivers.common.RPCException,
                publisher.publish_samples,
                mock.MagicMock(), self.test_data)
            self.assertTrue(mylog.info.called)
            self.assertEqual(0, len(publisher.local_queue))
            prepare.assert_called_once_with(
                topic=self.CONF.publisher_rpc.metering_topic)

    @mock.patch('ceilometer.publisher.rpc.LOG')
    def test_published_with_policy_incorrect(self, mylog):
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://?policy=notexist'))
        side_effect = oslo.messaging._drivers.common.RPCException()
        with mock.patch.object(publisher.rpc_client, 'prepare') as prepare:
            prepare.side_effect = side_effect
            self.assertRaises(
                oslo.messaging._drivers.common.RPCException,
                publisher.publish_samples,
                mock.MagicMock(), self.test_data)
            self.assertTrue(mylog.warn.called)
            self.assertEqual('default', publisher.policy)
            self.assertEqual(0, len(publisher.local_queue))
            prepare.assert_called_once_with(
                topic=self.CONF.publisher_rpc.metering_topic)

    def test_published_with_policy_drop_and_rpc_down(self):
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://?policy=drop'))
        side_effect = oslo.messaging._drivers.common.RPCException()
        with mock.patch.object(publisher.rpc_client, 'prepare') as prepare:
            prepare.side_effect = side_effect
            publisher.publish_samples(mock.MagicMock(),
                                      self.test_data)
            self.assertEqual(0, len(publisher.local_queue))
            prepare.assert_called_once_with(
                topic=self.CONF.publisher_rpc.metering_topic)

    def test_published_with_policy_queue_and_rpc_down(self):
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://?policy=queue'))
        side_effect = oslo.messaging._drivers.common.RPCException()
        with mock.patch.object(publisher.rpc_client, 'prepare') as prepare:
            prepare.side_effect = side_effect

            publisher.publish_samples(mock.MagicMock(),
                                      self.test_data)
            self.assertEqual(1, len(publisher.local_queue))
            prepare.assert_called_once_with(
                topic=self.CONF.publisher_rpc.metering_topic)

    def test_published_with_policy_queue_and_rpc_down_up(self):
        self.rpc_unreachable = True
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://?policy=queue'))

        side_effect = oslo.messaging._drivers.common.RPCException()
        with mock.patch.object(publisher.rpc_client, 'prepare') as prepare:
            prepare.side_effect = side_effect
            publisher.publish_samples(mock.MagicMock(),
                                      self.test_data)

            self.assertEqual(1, len(publisher.local_queue))

            prepare.side_effect = mock.MagicMock()
            publisher.publish_samples(mock.MagicMock(),
                                      self.test_data)

            self.assertEqual(0, len(publisher.local_queue))

            topic = self.CONF.publisher_rpc.metering_topic
            expected = [mock.call(topic=topic),
                        mock.call(topic=topic),
                        mock.call(topic=topic)]
            self.assertEqual(expected, prepare.mock_calls)

    def test_published_with_policy_sized_queue_and_rpc_down(self):
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://?policy=queue&max_queue_length=3'))

        side_effect = oslo.messaging._drivers.common.RPCException()
        with mock.patch.object(publisher.rpc_client, 'prepare') as prepare:
            prepare.side_effect = side_effect
            for i in range(0, 5):
                for s in self.test_data:
                    s.source = 'test-%d' % i
                publisher.publish_samples(mock.MagicMock(),
                                          self.test_data)

        self.assertEqual(3, len(publisher.local_queue))
        self.assertEqual(
            'test-2',
            publisher.local_queue[0][2][0]['source']
        )
        self.assertEqual(
            'test-3',
            publisher.local_queue[1][2][0]['source']
        )
        self.assertEqual(
            'test-4',
            publisher.local_queue[2][2][0]['source']
        )

    def test_published_with_policy_default_sized_queue_and_rpc_down(self):
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://?policy=queue'))

        side_effect = oslo.messaging._drivers.common.RPCException()
        with mock.patch.object(publisher.rpc_client, 'prepare') as prepare:
            prepare.side_effect = side_effect
            for i in range(0, 2000):
                for s in self.test_data:
                    s.source = 'test-%d' % i
                publisher.publish_samples(mock.MagicMock(),
                                          self.test_data)

        self.assertEqual(1024, len(publisher.local_queue))
        self.assertEqual(
            'test-976',
            publisher.local_queue[0][2][0]['source']
        )
        self.assertEqual(
            'test-1999',
            publisher.local_queue[1023][2][0]['source']
        )
