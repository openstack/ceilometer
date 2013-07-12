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
"""Tests for ceilometer/publish.py
"""

import datetime
from oslo.config import cfg

from ceilometer import counter
from ceilometer.openstack.common import jsonutils
from ceilometer.openstack.common import network_utils
from ceilometer.openstack.common import rpc as oslo_rpc
from ceilometer.publisher import rpc
from ceilometer.tests import base


class TestSignature(base.TestCase):

    def test_compute_signature_change_key(self):
        sig1 = rpc.compute_signature({'a': 'A', 'b': 'B'},
                                     'not-so-secret')
        sig2 = rpc.compute_signature({'A': 'A', 'b': 'B'},
                                     'not-so-secret')
        self.assertNotEqual(sig1, sig2)

    def test_compute_signature_change_value(self):
        sig1 = rpc.compute_signature({'a': 'A', 'b': 'B'},
                                     'not-so-secret')
        sig2 = rpc.compute_signature({'a': 'a', 'b': 'B'},
                                     'not-so-secret')
        self.assertNotEqual(sig1, sig2)

    def test_compute_signature_same(self):
        sig1 = rpc.compute_signature({'a': 'A', 'b': 'B'},
                                     'not-so-secret')
        sig2 = rpc.compute_signature({'a': 'A', 'b': 'B'},
                                     'not-so-secret')
        self.assertEqual(sig1, sig2)

    def test_compute_signature_signed(self):
        data = {'a': 'A', 'b': 'B'}
        sig1 = rpc.compute_signature(data, 'not-so-secret')
        data['message_signature'] = sig1
        sig2 = rpc.compute_signature(data, 'not-so-secret')
        self.assertEqual(sig1, sig2)

    def test_compute_signature_use_configured_secret(self):
        data = {'a': 'A', 'b': 'B'}
        sig1 = rpc.compute_signature(data, 'not-so-secret')
        sig2 = rpc.compute_signature(data, 'different-value')
        self.assertNotEqual(sig1, sig2)

    def test_verify_signature_signed(self):
        data = {'a': 'A', 'b': 'B'}
        sig1 = rpc.compute_signature(data, 'not-so-secret')
        data['message_signature'] = sig1
        self.assertTrue(rpc.verify_signature(data, 'not-so-secret'))

    def test_verify_signature_unsigned(self):
        data = {'a': 'A', 'b': 'B'}
        self.assertFalse(rpc.verify_signature(data, 'not-so-secret'))

    def test_verify_signature_incorrect(self):
        data = {'a': 'A', 'b': 'B',
                'message_signature': 'Not the same'}
        self.assertFalse(rpc.verify_signature(data, 'not-so-secret'))

    def test_verify_signature_nested(self):
        data = {'a': 'A',
                'b': 'B',
                'nested': {'a': 'A',
                           'b': 'B',
                           },
                }
        data['message_signature'] = rpc.compute_signature(
            data,
            'not-so-secret')
        self.assertTrue(rpc.verify_signature(data, 'not-so-secret'))

    def test_verify_signature_nested_json(self):
        data = {'a': 'A',
                'b': 'B',
                'nested': {'a': 'A',
                           'b': 'B',
                           'c': ('c',),
                           'd': ['d']
                           },
                }
        data['message_signature'] = rpc.compute_signature(
            data,
            'not-so-secret')
        jsondata = jsonutils.loads(jsonutils.dumps(data))
        self.assertTrue(rpc.verify_signature(jsondata, 'not-so-secret'))


class TestCounter(base.TestCase):

    TEST_COUNTER = counter.Counter(name='name',
                                   type='typ',
                                   unit='',
                                   volume=1,
                                   user_id='user',
                                   project_id='project',
                                   resource_id=2,
                                   timestamp='today',
                                   resource_metadata={'key': 'value'},
                                   )

    def test_meter_message_from_counter_signed(self):
        msg = rpc.meter_message_from_counter(self.TEST_COUNTER,
                                             'not-so-secret',
                                             'src')
        self.assertIn('message_signature', msg)

    def test_meter_message_from_counter_field(self):
        def compare(f, c, msg_f, msg):
            self.assertEqual(msg, c)
        msg = rpc.meter_message_from_counter(self.TEST_COUNTER,
                                             'not-so-secret',
                                             'src')
        name_map = {'name': 'counter_name',
                    'type': 'counter_type',
                    'unit': 'counter_unit',
                    'volume': 'counter_volume'}
        for f in self.TEST_COUNTER._fields:
            msg_f = name_map.get(f, f)
            yield compare, f, getattr(self.TEST_COUNTER, f), msg_f, msg[msg_f]


class TestPublish(base.TestCase):

    test_data = [
        counter.Counter(
            name='test',
            type=counter.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
        counter.Counter(
            name='test',
            type=counter.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
        counter.Counter(
            name='test2',
            type=counter.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
        counter.Counter(
            name='test2',
            type=counter.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id='test_run_tasks',
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
        counter.Counter(
            name='test3',
            type=counter.TYPE_CUMULATIVE,
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
        self.published.append((topic, msg))

    def setUp(self):
        super(TestPublish, self).setUp()
        self.published = []
        self.stubs.Set(oslo_rpc, 'cast', self.faux_cast)

    def test_published(self):
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://'))
        publisher.publish_counters(None,
                                   self.test_data,
                                   'test')
        self.assertEqual(len(self.published), 1)
        self.assertEqual(self.published[0][0],
                         cfg.CONF.publisher_rpc.metering_topic)
        self.assertIsInstance(self.published[0][1]['args']['data'], list)

    def test_published_with_per_meter_topic(self):
        publisher = rpc.RPCPublisher(
            network_utils.urlsplit('rpc://?per_meter_topic=1'))
        publisher.publish_counters(None,
                                   self.test_data,
                                   'test')
        self.assertEqual(len(self.published), 4)
        for topic, rpc_call in self.published:
            meters = rpc_call['args']['data']
            self.assertIsInstance(meters, list)
            if topic != cfg.CONF.publisher_rpc.metering_topic:
                self.assertEqual(len(set(meter['counter_name']
                                         for meter in meters)),
                                 1,
                                 "Meter are published grouped by name")

        topics = [topic for topic, meter in self.published]
        self.assertIn(cfg.CONF.publisher_rpc.metering_topic, topics)
        self.assertIn(
            cfg.CONF.publisher_rpc.metering_topic + '.' + 'test', topics)
        self.assertIn(
            cfg.CONF.publisher_rpc.metering_topic + '.' + 'test2', topics)
        self.assertIn(
            cfg.CONF.publisher_rpc.metering_topic + '.' + 'test3', topics)
