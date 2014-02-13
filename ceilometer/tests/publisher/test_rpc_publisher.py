# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
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
import fixtures
import mock

from ceilometer.openstack.common.fixture import config
from ceilometer.openstack.common import network_utils
from ceilometer.openstack.common import test
from ceilometer.publisher import rpc
from ceilometer import sample


class TestPublish(test.BaseTestCase):
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

    def faux_cast(self, context, topic, msg):
        if self.rpc_unreachable:
            #note(sileht): Ugly, but when rabbitmq is unreachable
            # and rabbitmq_max_retries is not 0
            # oslo.rpc do a sys.exit(1), so we do the same
            # things here until this is fixed in oslo
            raise SystemExit(1)
        else:
            self.published.append((topic, msg))

    def setUp(self):
        super(TestPublish, self).setUp()
        self.CONF = self.useFixture(config.Config()).conf
        self.published = []
        self.rpc_unreachable = False
        self.useFixture(fixtures.MonkeyPatch(
            "ceilometer.openstack.common.rpc.cast",
            self.faux_cast))

    def test_published(self):
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://'))
        publisher.publish_samples(None,
                                  self.test_data)
        self.assertEqual(len(self.published), 1)
        self.assertEqual(self.published[0][0],
                         self.CONF.publisher_rpc.metering_topic)
        self.assertIsInstance(self.published[0][1]['args']['data'], list)
        self.assertEqual(self.published[0][1]['method'],
                         'record_metering_data')

    def test_publish_target(self):
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://?target=custom_procedure_call'))
        publisher.publish_samples(None,
                                  self.test_data)
        self.assertEqual(len(self.published), 1)
        self.assertEqual(self.published[0][0],
                         self.CONF.publisher_rpc.metering_topic)
        self.assertIsInstance(self.published[0][1]['args']['data'], list)
        self.assertEqual(self.published[0][1]['method'],
                         'custom_procedure_call')

    def test_published_with_per_meter_topic(self):
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://?per_meter_topic=1'))
        publisher.publish_samples(None,
                                  self.test_data)
        self.assertEqual(len(self.published), 4)
        for topic, rpc_call in self.published:
            meters = rpc_call['args']['data']
            self.assertIsInstance(meters, list)
            if topic != self.CONF.publisher_rpc.metering_topic:
                self.assertEqual(len(set(meter['counter_name']
                                         for meter in meters)),
                                 1,
                                 "Meter are published grouped by name")

        topics = [topic for topic, meter in self.published]
        self.assertIn(self.CONF.publisher_rpc.metering_topic, topics)
        self.assertIn(
            self.CONF.publisher_rpc.metering_topic + '.' + 'test', topics)
        self.assertIn(
            self.CONF.publisher_rpc.metering_topic + '.' + 'test2', topics)
        self.assertIn(
            self.CONF.publisher_rpc.metering_topic + '.' + 'test3', topics)

    def test_published_concurrency(self):
        """This test the concurrent access to the local queue
        of the rpc publisher
        """

        def faux_cast_go(context, topic, msg):
            self.published.append((topic, msg))

        def faux_cast_wait(context, topic, msg):
            self.useFixture(fixtures.MonkeyPatch(
                "ceilometer.openstack.common.rpc.cast",
                faux_cast_go))
            # Sleep to simulate concurrency and allow other threads to work
            eventlet.sleep(0)
            self.published.append((topic, msg))

        self.useFixture(fixtures.MonkeyPatch(
            "ceilometer.openstack.common.rpc.cast",
            faux_cast_wait))

        publisher = rpc.RPCPublisher(network_utils.urlsplit('rpc://'))
        job1 = eventlet.spawn(publisher.publish_samples, None, self.test_data)
        job2 = eventlet.spawn(publisher.publish_samples, None, self.test_data)

        job1.wait()
        job2.wait()

        self.assertEqual(publisher.policy, 'default')
        self.assertEqual(len(self.published), 2)
        self.assertEqual(len(publisher.local_queue), 0)

    @mock.patch('ceilometer.publisher.rpc.LOG')
    def test_published_with_no_policy(self, mylog):
        self.rpc_unreachable = True
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://'))
        self.assertTrue(mylog.info.called)

        self.assertRaises(
            SystemExit,
            publisher.publish_samples,
            None, self.test_data)
        self.assertEqual(publisher.policy, 'default')
        self.assertEqual(len(self.published), 0)
        self.assertEqual(len(publisher.local_queue), 0)

    @mock.patch('ceilometer.publisher.rpc.LOG')
    def test_published_with_policy_block(self, mylog):
        self.rpc_unreachable = True
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://?policy=default'))
        self.assertTrue(mylog.info.called)
        self.assertRaises(
            SystemExit,
            publisher.publish_samples,
            None, self.test_data)
        self.assertEqual(len(self.published), 0)
        self.assertEqual(len(publisher.local_queue), 0)

    @mock.patch('ceilometer.publisher.rpc.LOG')
    def test_published_with_policy_incorrect(self, mylog):
        self.rpc_unreachable = True
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://?policy=notexist'))
        self.assertRaises(
            SystemExit,
            publisher.publish_samples,
            None, self.test_data)
        self.assertTrue(mylog.warn.called)
        self.assertEqual(publisher.policy, 'default')
        self.assertEqual(len(self.published), 0)
        self.assertEqual(len(publisher.local_queue), 0)

    def test_published_with_policy_drop_and_rpc_down(self):
        self.rpc_unreachable = True
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://?policy=drop'))
        publisher.publish_samples(None,
                                  self.test_data)
        self.assertEqual(len(self.published), 0)
        self.assertEqual(len(publisher.local_queue), 0)

    def test_published_with_policy_queue_and_rpc_down(self):
        self.rpc_unreachable = True
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://?policy=queue'))
        publisher.publish_samples(None,
                                  self.test_data)
        self.assertEqual(len(self.published), 0)
        self.assertEqual(len(publisher.local_queue), 1)

    def test_published_with_policy_queue_and_rpc_down_up(self):
        self.rpc_unreachable = True
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://?policy=queue'))
        publisher.publish_samples(None,
                                  self.test_data)
        self.assertEqual(len(self.published), 0)
        self.assertEqual(len(publisher.local_queue), 1)

        self.rpc_unreachable = False
        publisher.publish_samples(None,
                                  self.test_data)

        self.assertEqual(len(self.published), 2)
        self.assertEqual(len(publisher.local_queue), 0)

    def test_published_with_policy_sized_queue_and_rpc_down(self):
        self.rpc_unreachable = True
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://?policy=queue&max_queue_length=3'))
        for i in range(5):
            for s in self.test_data:
                s.source = 'test-%d' % i
            publisher.publish_samples(None,
                                      self.test_data)
        self.assertEqual(len(self.published), 0)
        self.assertEqual(len(publisher.local_queue), 3)
        self.assertEqual(
            publisher.local_queue[0][2]['args']['data'][0]['source'],
            'test-2'
        )
        self.assertEqual(
            publisher.local_queue[1][2]['args']['data'][0]['source'],
            'test-3'
        )
        self.assertEqual(
            publisher.local_queue[2][2]['args']['data'][0]['source'],
            'test-4'
        )

    def test_published_with_policy_default_sized_queue_and_rpc_down(self):
        self.rpc_unreachable = True
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://?policy=queue'))
        for i in range(2000):
            for s in self.test_data:
                s.source = 'test-%d' % i
            publisher.publish_samples(None,
                                      self.test_data)
        self.assertEqual(len(self.published), 0)
        self.assertEqual(len(publisher.local_queue), 1024)
        self.assertEqual(
            publisher.local_queue[0][2]['args']['data'][0]['source'],
            'test-976'
        )
        self.assertEqual(
            publisher.local_queue[1023][2]['args']['data'][0]['source'],
            'test-1999'
        )
