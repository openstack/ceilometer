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
"""Tests for ceilometer/agent/service.py
"""

import socket

import mock
from mock import patch
import msgpack
from stevedore import extension
from stevedore.tests import manager as test_manager

from ceilometer.collector import service
from ceilometer.openstack.common.fixture import config
from ceilometer import sample
from ceilometer.tests import base as tests_base


class TestCollector(tests_base.BaseTestCase):
    def setUp(self):
        super(TestCollector, self).setUp()
        self.CONF = self.useFixture(config.Config()).conf
        self.CONF.set_override("connection", "log://", group='database')


class TestUDPCollectorService(TestCollector):
    def _make_fake_socket(self):
        def recvfrom(size):
            # Make the loop stop
            self.srv.stop()
            return (msgpack.dumps(self.counter), ('127.0.0.1', 12345))

        sock = mock.Mock()
        sock.recvfrom = recvfrom
        return sock

    def _verify_udp_socket(self, udp_socket):
        conf = self.CONF.collector
        udp_socket.setsockopt.assert_called_once_with(socket.SOL_SOCKET,
                                                      socket.SO_REUSEADDR, 1)
        udp_socket.bind.assert_called_once_with((conf.udp_address,
                                                 conf.udp_port))

    def setUp(self):
        super(TestUDPCollectorService, self).setUp()
        self.srv = service.UDPCollectorService()
        self.counter = sample.Sample(
            name='foobar',
            type='bad',
            unit='F',
            volume=1,
            user_id='jd',
            project_id='ceilometer',
            resource_id='cat',
            timestamp='NOW!',
            resource_metadata={},
        ).as_dict()

    def test_udp_receive(self):
        mock_dispatcher = mock.MagicMock()
        self.srv.dispatcher_manager = test_manager.TestExtensionManager(
            [extension.Extension('test',
                                 None,
                                 None,
                                 mock_dispatcher
                                 ),
             ])
        self.counter['source'] = 'mysource'
        self.counter['counter_name'] = self.counter['name']
        self.counter['counter_volume'] = self.counter['volume']
        self.counter['counter_type'] = self.counter['type']
        self.counter['counter_unit'] = self.counter['unit']

        udp_socket = self._make_fake_socket()
        with patch('socket.socket', return_value=udp_socket):
            self.srv.start()

        self._verify_udp_socket(udp_socket)

        mock_dispatcher.record_metering_data.assert_called_once_with(
            self.counter)

    def test_udp_receive_storage_error(self):
        mock_dispatcher = mock.MagicMock()
        self.srv.dispatcher_manager = test_manager.TestExtensionManager(
            [extension.Extension('test',
                                 None,
                                 None,
                                 mock_dispatcher
                                 ),
             ])
        mock_dispatcher.record_metering_data.side_effect = self._raise_error

        self.counter['source'] = 'mysource'
        self.counter['counter_name'] = self.counter['name']
        self.counter['counter_volume'] = self.counter['volume']
        self.counter['counter_type'] = self.counter['type']
        self.counter['counter_unit'] = self.counter['unit']

        udp_socket = self._make_fake_socket()
        with patch('socket.socket', return_value=udp_socket):
            self.srv.start()

        self._verify_udp_socket(udp_socket)

        mock_dispatcher.record_metering_data.assert_called_once_with(
            self.counter)

    @staticmethod
    def _raise_error():
        raise Exception

    def test_udp_receive_bad_decoding(self):
        udp_socket = self._make_fake_socket()
        with patch('socket.socket', return_value=udp_socket):
            with patch('msgpack.loads', self._raise_error):
                self.srv.start()

        self._verify_udp_socket(udp_socket)


class TestCollectorService(TestCollector):

    def setUp(self):
        super(TestCollectorService, self).setUp()
        self.srv = service.CollectorService('the-host', 'the-topic')

    @patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_init_host(self):
        # If we try to create a real RPC connection, init_host() never
        # returns. Mock it out so we can establish the service
        # configuration.
        with patch('ceilometer.openstack.common.rpc.create_connection'):
            self.srv.start()
