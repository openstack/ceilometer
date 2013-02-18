# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
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

from ceilometer.openstack.common import rpc
from ceilometer.tests import base

from ceilometer import counter
from ceilometer.publisher import meter_publish


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
        self.stubs.Set(rpc, 'cast', self.faux_cast)
        publisher = meter_publish.MeterPublisher()
        publisher.publish_counters(None,
                                   self.test_data,
                                   'test')

    def test_published(self):
        self.assertEqual(len(self.published), 4)
        for topic, rpc_call in self.published:
            meters = rpc_call['args']['data']
            self.assertIsInstance(meters, list)
            if topic != cfg.CONF.metering_topic:
                self.assertEqual(len(set(meter['counter_name']
                                         for meter in meters)),
                                 1,
                                 "Meter are published grouped by name")

    def test_published_topics(self):
        topics = [topic for topic, meter in self.published]
        self.assertIn(cfg.CONF.metering_topic, topics)
        self.assertIn(cfg.CONF.metering_topic + '.' + 'test', topics)
        self.assertIn(cfg.CONF.metering_topic + '.' + 'test2', topics)
        self.assertIn(cfg.CONF.metering_topic + '.' + 'test3', topics)
