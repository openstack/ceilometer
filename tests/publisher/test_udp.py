# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance
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

from ceilometer import sample
from ceilometer.publisher import udp
from ceilometer.openstack.common import test
from ceilometer.openstack.common import network_utils
from ceilometer.openstack.common.fixture import config
from ceilometer.openstack.common.fixture import moxstubout


COUNTER_SOURCE = 'testsource'


class TestUDPPublisher(test.BaseTestCase):

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
            udp_socket = self.mox.CreateMockAnything()
            udp_socket.sendto = record_data
            self.mox.ReplayAll()
            return udp_socket
        return _fake_socket_socket

    def setUp(self):
        super(TestUDPPublisher, self).setUp()
        self.mox = self.useFixture(moxstubout.MoxStubout()).mox
        self.CONF = self.useFixture(config.Config()).conf

    def test_published(self):
        self.data_sent = []
        with mock.patch('socket.socket',
                        self._make_fake_socket(self.data_sent)):
            publisher = udp.UDPPublisher(
                network_utils.urlsplit('udp://somehost'))
        publisher.publish_samples(None,
                                  self.test_data)

        self.assertEqual(len(self.data_sent), 5)

        sent_counters = []

        for data, dest in self.data_sent:
            counter = msgpack.loads(data)
            sent_counters.append(counter)

            # Check destination
            self.assertEqual(dest, ('somehost',
                                    self.CONF.collector.udp_port))

        # Check that counters are equal
        self.assertEqual(sorted(sent_counters),
                         sorted([dict(d.as_dict()) for d in self.test_data]))

    @staticmethod
    def _raise_ioerror():
        raise IOError

    def _make_broken_socket(self, family, type):
        udp_socket = self.mox.CreateMockAnything()
        udp_socket.sendto = self._raise_ioerror
        self.mox.ReplayAll()

    def test_publish_error(self):
        with mock.patch('socket.socket',
                        self._make_broken_socket):
            publisher = udp.UDPPublisher(
                network_utils.urlsplit('udp://localhost'))
        publisher.publish_samples(None,
                                  self.test_data)
