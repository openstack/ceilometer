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
import socket

import mock
from mock import patch
import msgpack
from stevedore import extension

from ceilometer import collector
from ceilometer.openstack.common.fixture import config
from ceilometer import sample
from ceilometer.tests import base as tests_base


class FakeConnection():
    def create_worker(self, topic, proxy, pool_name):
        pass


class TestCollector(tests_base.BaseTestCase):
    def setUp(self):
        super(TestCollector, self).setUp()
        self.CONF = self.useFixture(config.Config()).conf
        self.CONF.set_override("connection", "log://", group='database')
        self.srv = collector.CollectorService('the-host', 'the-topic')
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

    def _make_test_manager(self, plugin):
        return extension.ExtensionManager.make_test_instance([
            extension.Extension(
                'test',
                None,
                None,
                plugin,
            ),
        ])

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

    def test_record_metering_data(self):
        mock_dispatcher = mock.MagicMock()
        self.srv.dispatcher_manager = self._make_test_manager(mock_dispatcher)

        self.srv.record_metering_data(None, self.counter)

        mock_dispatcher.record_metering_data.assert_called_once_with(
            data=self.counter)

    def test_udp_receive(self):
        mock_dispatcher = mock.MagicMock()
        self.srv.dispatcher_manager = self._make_test_manager(mock_dispatcher)
        self.counter['source'] = 'mysource'
        self.counter['counter_name'] = self.counter['name']
        self.counter['counter_volume'] = self.counter['volume']
        self.counter['counter_type'] = self.counter['type']
        self.counter['counter_unit'] = self.counter['unit']

        udp_socket = self._make_fake_socket()
        with patch('socket.socket', return_value=udp_socket):
            self.srv.start_udp()

        self._verify_udp_socket(udp_socket)

        mock_dispatcher.record_metering_data.assert_called_once_with(
            self.counter)

    def test_udp_receive_storage_error(self):
        mock_dispatcher = mock.MagicMock()
        self.srv.dispatcher_manager = self._make_test_manager(mock_dispatcher)
        mock_dispatcher.record_metering_data.side_effect = self._raise_error

        self.counter['source'] = 'mysource'
        self.counter['counter_name'] = self.counter['name']
        self.counter['counter_volume'] = self.counter['volume']
        self.counter['counter_type'] = self.counter['type']
        self.counter['counter_unit'] = self.counter['unit']

        udp_socket = self._make_fake_socket()
        with patch('socket.socket', return_value=udp_socket):
            self.srv.start_udp()

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
                self.srv.start_udp()

        self._verify_udp_socket(udp_socket)

    @patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    @patch('ceilometer.event.converter.setup_events', mock.MagicMock())
    def test_init_host(self):
        # If we try to create a real RPC connection, init_host() never
        # returns. Mock it out so we can establish the service
        # configuration.
        with patch('ceilometer.openstack.common.rpc.create_connection'):
            self.srv.start()

    def test_only_udp(self):
        """Check that only UDP is started if rpc_backend is empty."""
        self.CONF.set_override('rpc_backend', '')
        udp_socket = self._make_fake_socket()
        with patch('socket.socket', return_value=udp_socket):
            self.srv.start()

    def test_only_rpc(self):
        """Check that only RPC is started if udp_address is empty."""
        self.CONF.set_override('udp_address', '', group='collector')
        with patch('ceilometer.openstack.common.rpc.create_connection'):
            self.srv.start()

    @patch.object(FakeConnection, 'create_worker')
    @patch('ceilometer.openstack.common.rpc.dispatcher.RpcDispatcher')
    def test_initialize_service_hook_conf_opt(self, mock_dispatcher,
                                              mock_worker):
        self.CONF.set_override('metering_topic', 'mytopic',
                               group='publisher_rpc')
        self.srv.conn = FakeConnection()
        self.srv.initialize_service_hook(mock.MagicMock())
        mock_worker.assert_called_once_with('mytopic', mock_dispatcher(),
                                            'ceilometer.collector.mytopic')
