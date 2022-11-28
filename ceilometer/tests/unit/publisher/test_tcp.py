#
# Copyright 2022 Red Hat, Inc
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
"""Tests for ceilometer/publisher/tcp.py"""

import datetime
from unittest import mock

import msgpack
from oslo_utils import netutils
from oslotest import base

from ceilometer.publisher import tcp
from ceilometer.publisher import utils
from ceilometer import sample
from ceilometer import service


COUNTER_SOURCE = 'testsource'


class TestTCPPublisher(base.BaseTestCase):
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

    @staticmethod
    def _make_fake_socket(published):
        def _fake_socket_socket(family, type):
            def record_data(msg):
                msg_length = int.from_bytes(msg[0:8], "little")
                published.append(msg[8:msg_length + 8])

            def connect(dst):
                pass

            tcp_socket = mock.Mock()
            tcp_socket.send = record_data
            tcp_socket.connect = connect
            return tcp_socket

        return _fake_socket_socket

    def setUp(self):
        super(TestTCPPublisher, self).setUp()
        self.CONF = service.prepare_service([], [])
        self.CONF.publisher.telemetry_secret = 'not-so-secret'

    def test_published(self):
        self.data_sent = []
        with mock.patch('socket.socket',
                        self._make_fake_socket(self.data_sent)):
            publisher = tcp.TCPPublisher(
                self.CONF,
                netutils.urlsplit('tcp://somehost'))
        publisher.publish_samples(self.test_data)

        self.assertEqual(5, len(self.data_sent))

        sent_counters = []

        for data in self.data_sent:
            counter = msgpack.loads(data, raw=False)
            sent_counters.append(counter)

        # Check that counters are equal
        def sort_func(counter):
            return counter['counter_name']

        counters = [utils.meter_message_from_counter(d,
                                                     "not-so-secret",
                                                     publisher.conf.host)
                    for d in self.test_data]
        counters.sort(key=sort_func)
        sent_counters.sort(key=sort_func)
        self.assertEqual(counters, sent_counters)

    @staticmethod
    def _make_disconnecting_socket(published, connections):
        def _fake_socket_socket(family, type):
            def record_data(msg):
                if len(published) == len(connections) - 1:
                    # Raise for every each first send attempt to
                    # trigger a reconnection attempt and send the data
                    # correctly after reconnecting
                    raise IOError
                msg_length = int.from_bytes(msg[0:8], "little")
                published.append(msg[8:msg_length + 8])

            def record_connection(dest):
                connections.append(dest)

            tcp_socket = mock.Mock()
            tcp_socket.send = record_data
            tcp_socket.connect = record_connection
            return tcp_socket

        return _fake_socket_socket

    def test_reconnect(self):
        self.data_sent = []
        self.connections = []
        with mock.patch('socket.socket',
                        self._make_disconnecting_socket(self.data_sent,
                                                        self.connections)):
            publisher = tcp.TCPPublisher(
                self.CONF,
                netutils.urlsplit('tcp://somehost'))
            publisher.publish_samples(self.test_data)

        sent_counters = []

        for data in self.data_sent:
            counter = msgpack.loads(data, raw=False)
            sent_counters.append(counter)

        for connection in self.connections:
            # Check destination
            self.assertEqual(('somehost', 4952), connection)
        self.assertEqual(len(self.connections) - 1, len(self.data_sent))

        # Check that counters are equal
        def sort_func(counter):
            return counter['counter_name']

        counters = [utils.meter_message_from_counter(d,
                                                     "not-so-secret",
                                                     publisher.conf.host)
                    for d in self.test_data]
        counters.sort(key=sort_func)
        sent_counters.sort(key=sort_func)
        self.assertEqual(counters, sent_counters)

    @staticmethod
    def _raise_ioerror(*args):
        raise IOError

    def _make_broken_socket(self, family, type):
        def connect(dst):
            pass

        tcp_socket = mock.Mock()
        tcp_socket.send = self._raise_ioerror
        tcp_socket.connect = connect
        return tcp_socket

    def test_publish_error(self):
        with mock.patch('socket.socket',
                        self._make_broken_socket):
            publisher = tcp.TCPPublisher(
                self.CONF,
                netutils.urlsplit('tcp://localhost'))
            publisher.publish_samples(self.test_data)
