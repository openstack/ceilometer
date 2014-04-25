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
import contextlib
import socket

import mock
import msgpack
import oslo.messaging
from stevedore import extension

from ceilometer import collector
from ceilometer import messaging
from ceilometer.openstack.common.fixture import config
from ceilometer.publisher import utils
from ceilometer import sample
from ceilometer.tests import base as tests_base


class FakeConnection():
    def create_worker(self, topic, proxy, pool_name):
        pass


class TestCollector(tests_base.BaseTestCase):
    def setUp(self):
        super(TestCollector, self).setUp()
        messaging.setup('fake://')
        self.addCleanup(messaging.cleanup)
        self.CONF = self.useFixture(config.Config()).conf
        self.CONF.set_override("connection", "log://", group='database')
        self.srv = collector.CollectorService()
        self.CONF.publisher.metering_secret = 'not-so-secret'
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

        self.utf8_msg = utils.meter_message_from_counter(
            sample.Sample(
                name=u'test',
                type=sample.TYPE_CUMULATIVE,
                unit=u'',
                volume=1,
                user_id=u'test',
                project_id=u'test',
                resource_id=u'test_run_tasks',
                timestamp=u'NOW!',
                resource_metadata={u'name': [([u'TestPublish'])]},
                source=u'testsource',
            ),
            'not-so-secret')

    def _make_test_manager(self, plugin):
        return extension.ExtensionManager.make_test_instance([
            extension.Extension(
                'test',
                None,
                None,
                plugin,
            ),
        ])

    def _make_fake_socket(self, sample):
        def recvfrom(size):
            # Make the loop stop
            self.srv.stop()
            return msgpack.dumps(sample), ('127.0.0.1', 12345)

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
        self.CONF.set_override('rpc_backend', '')
        mock_dispatcher = mock.MagicMock()
        self.srv.dispatcher_manager = self._make_test_manager(mock_dispatcher)
        self.counter['source'] = 'mysource'
        self.counter['counter_name'] = self.counter['name']
        self.counter['counter_volume'] = self.counter['volume']
        self.counter['counter_type'] = self.counter['type']
        self.counter['counter_unit'] = self.counter['unit']

        udp_socket = self._make_fake_socket(self.counter)
        with mock.patch('socket.socket', return_value=udp_socket):
            self.srv.start_udp()

        self._verify_udp_socket(udp_socket)

        mock_dispatcher.record_metering_data.assert_called_once_with(
            self.counter)

    def test_udp_receive_storage_error(self):
        self.CONF.set_override('rpc_backend', '')
        mock_dispatcher = mock.MagicMock()
        self.srv.dispatcher_manager = self._make_test_manager(mock_dispatcher)
        mock_dispatcher.record_metering_data.side_effect = self._raise_error

        self.counter['source'] = 'mysource'
        self.counter['counter_name'] = self.counter['name']
        self.counter['counter_volume'] = self.counter['volume']
        self.counter['counter_type'] = self.counter['type']
        self.counter['counter_unit'] = self.counter['unit']

        udp_socket = self._make_fake_socket(self.counter)
        with mock.patch('socket.socket', return_value=udp_socket):
            self.srv.start_udp()

        self._verify_udp_socket(udp_socket)

        mock_dispatcher.record_metering_data.assert_called_once_with(
            self.counter)

    @staticmethod
    def _raise_error():
        raise Exception

    def test_udp_receive_bad_decoding(self):
        self.CONF.set_override('rpc_backend', '')
        udp_socket = self._make_fake_socket(self.counter)
        with mock.patch('socket.socket', return_value=udp_socket):
            with mock.patch('msgpack.loads', self._raise_error):
                self.srv.start_udp()

        self._verify_udp_socket(udp_socket)

    @staticmethod
    def _dummy_thread_group_add_thread(method):
        method()

    @mock.patch.object(oslo.messaging.MessageHandlingServer, 'start')
    @mock.patch.object(collector.CollectorService, 'start_udp')
    def test_only_udp(self, udp_start, rpc_start):
        """Check that only UDP is started if rpc_backend is empty."""
        self.CONF.set_override('rpc_backend', '')
        udp_socket = self._make_fake_socket(self.counter)
        with contextlib.nested(
                mock.patch.object(
                    self.srv.tg, 'add_thread',
                    side_effect=self._dummy_thread_group_add_thread),
                mock.patch('socket.socket', return_value=udp_socket)):
            self.srv.start()
            self.assertEqual(0, rpc_start.call_count)
            self.assertEqual(1, udp_start.call_count)

    @mock.patch.object(oslo.messaging.MessageHandlingServer, 'start')
    @mock.patch.object(collector.CollectorService, 'start_udp')
    def test_only_rpc(self, udp_start, rpc_start):
        """Check that only RPC is started if udp_address is empty."""
        self.CONF.set_override('udp_address', '', group='collector')
        with mock.patch.object(
                self.srv.tg, 'add_thread',
                side_effect=self._dummy_thread_group_add_thread):
            self.srv.start()
            self.assertEqual(1, rpc_start.call_count)
            self.assertEqual(0, udp_start.call_count)

    def test_udp_receive_valid_encoding(self):
        self.data_sent = []
        with mock.patch('socket.socket',
                        return_value=self._make_fake_socket(self.utf8_msg)):
            self.srv.rpc_server = mock.MagicMock()
            mock_dispatcher = mock.MagicMock()
            self.srv.dispatcher_manager = \
                self._make_test_manager(mock_dispatcher)
            self.srv.start_udp()
            self.assertTrue(utils.verify_signature(
                mock_dispatcher.method_calls[0][1][0],
                "not-so-secret"))
