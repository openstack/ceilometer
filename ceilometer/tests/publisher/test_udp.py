#
# Copyright 2013-2014 eNovance
#
# Author: Julien Danjou <julien@danjou.info>
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
"""Tests for ceilometer/publisher/udp.py
"""

import datetime

import mock
import msgpack
from oslo.config import fixture as fixture_config
from oslo.utils import netutils
from oslotest import base

from ceilometer.publisher import udp
from ceilometer.publisher import utils
from ceilometer import sample


COUNTER_SOURCE = 'testsource'


class TestUDPPublisher(base.BaseTestCase):
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
            source=COUNTER_SOURCE,
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
            source=COUNTER_SOURCE,
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
            source=COUNTER_SOURCE,
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
            source=COUNTER_SOURCE,
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
            source=COUNTER_SOURCE,
        ),
    ]

    def _make_fake_socket(self, published):
        def _fake_socket_socket(family, type):
            def record_data(msg, dest):
                published.append((msg, dest))

            udp_socket = mock.Mock()
            udp_socket.sendto = record_data
            return udp_socket

        return _fake_socket_socket

    def setUp(self):
        super(TestUDPPublisher, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.CONF.publisher.metering_secret = 'not-so-secret'

    def test_published(self):
        self.data_sent = []
        with mock.patch('socket.socket',
                        self._make_fake_socket(self.data_sent)):
            publisher = udp.UDPPublisher(
                netutils.urlsplit('udp://somehost'))
        publisher.publish_samples(None,
                                  self.test_data)

        self.assertEqual(5, len(self.data_sent))

        sent_counters = []

        for data, dest in self.data_sent:
            counter = msgpack.loads(data)
            sent_counters.append(counter)

            # Check destination
            self.assertEqual(('somehost',
                              self.CONF.collector.udp_port), dest)

        # Check that counters are equal
        self.assertEqual(sorted(
            [utils.meter_message_from_counter(d, "not-so-secret")
             for d in self.test_data]), sorted(sent_counters))

    @staticmethod
    def _raise_ioerror(*args):
        raise IOError

    def _make_broken_socket(self, family, type):
        udp_socket = mock.Mock()
        udp_socket.sendto = self._raise_ioerror
        return udp_socket

    def test_publish_error(self):
        with mock.patch('socket.socket',
                        self._make_broken_socket):
            publisher = udp.UDPPublisher(
                netutils.urlsplit('udp://localhost'))
        publisher.publish_samples(None,
                                  self.test_data)
