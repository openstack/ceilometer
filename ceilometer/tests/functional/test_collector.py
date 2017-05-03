#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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

import fixtures
import mock
import msgpack
import oslo_messaging
from oslo_utils import timeutils
from stevedore import extension

from ceilometer import collector
from ceilometer import dispatcher
from ceilometer.publisher import utils
from ceilometer import sample
from ceilometer import service
from ceilometer.tests import base as tests_base


class FakeException(Exception):
    pass


class FakeConnection(object):
    def create_worker(self, topic, proxy, pool_name):
        pass


class TestCollector(tests_base.BaseTestCase):
    def setUp(self):
        super(TestCollector, self).setUp()
        self.CONF = service.prepare_service([], [])
        self.CONF.import_opt("connection", "oslo_db.options", group="database")
        self.CONF.set_override("connection", "log://", group='database')
        self.CONF.set_override('telemetry_secret', 'not-so-secret',
                               group='publisher')
        self._setup_messaging()

        self.sample = utils.meter_message_from_counter(
            sample.Sample(
                name='foobar',
                type='bad',
                unit='F',
                volume=1,
                user_id='jd',
                project_id='ceilometer',
                resource_id='cat',
                timestamp=timeutils.utcnow().isoformat(),
                resource_metadata={},
            ), self.CONF.publisher.telemetry_secret)

        self.utf8_msg = utils.meter_message_from_counter(
            sample.Sample(
                name=u'test',
                type=sample.TYPE_CUMULATIVE,
                unit=u'',
                volume=1,
                user_id=u'test',
                project_id=u'test',
                resource_id=u'test_run_tasks',
                timestamp=timeutils.utcnow().isoformat(),
                resource_metadata={u'name': [([u'TestPublish'])]},
                source=u'testsource',
            ),
            'not-so-secret')

        self.mock_dispatcher = self._setup_fake_dispatcher()
        self.srv = collector.CollectorService(0, self.CONF)

    def _setup_messaging(self, enabled=True):
        if enabled:
            self.setup_messaging(self.CONF)
        else:
            self.useFixture(fixtures.MockPatch(
                'ceilometer.messaging.get_transport',
                return_value=None))

    def _setup_fake_dispatcher(self):
        plugin = mock.MagicMock()
        fake_dispatcher = extension.ExtensionManager.make_test_instance([
            extension.Extension('test', None, None, plugin,),
        ], propagate_map_exceptions=True)
        self.useFixture(fixtures.MockPatch(
            'ceilometer.dispatcher.load_dispatcher_manager',
            return_value=(fake_dispatcher, fake_dispatcher)))
        return plugin

    def _make_fake_socket(self, sample):
        def recvfrom(size):
            # Make the loop stop
            self.srv.udp_run = False
            return msgpack.dumps(sample), ('127.0.0.1', 12345)

        sock = mock.Mock()
        sock.recvfrom = recvfrom
        return sock

    def _verify_udp_socket(self, udp_socket):
        conf = self.CONF.collector
        setsocketopt_calls = [mock.call.setsockopt(socket.SOL_SOCKET,
                                                   socket.SO_REUSEADDR, 1),
                              mock.call.setsockopt(socket.SOL_SOCKET,
                                                   socket.SO_REUSEPORT, 1)]
        udp_socket.setsockopt.assert_has_calls(setsocketopt_calls)
        udp_socket.bind.assert_called_once_with((conf.udp_address,
                                                 conf.udp_port))

    def test_udp_receive_base(self):
        self._setup_messaging(False)

        udp_socket = self._make_fake_socket(self.sample)

        with mock.patch('select.select', return_value=([udp_socket], [], [])):
            with mock.patch('socket.socket') as mock_socket:
                mock_socket.return_value = udp_socket
                self.srv.run()
                self.addCleanup(self.srv.terminate)
                self.srv.udp_thread.join(5)
                self.assertFalse(self.srv.udp_thread.is_alive())
                mock_socket.assert_called_with(socket.AF_INET,
                                               socket.SOCK_DGRAM)

        self._verify_udp_socket(udp_socket)
        mock_record = self.mock_dispatcher.record_metering_data
        mock_record.assert_called_once_with(self.sample)

    def test_udp_socket_ipv6(self):
        self._setup_messaging(False)
        self.CONF.set_override('udp_address', '::1', group='collector')
        sock = self._make_fake_socket(self.sample)

        with mock.patch('select.select', return_value=([sock], [], [])):
            with mock.patch.object(socket, 'socket') as mock_socket:
                mock_socket.return_value = sock
                self.srv.run()
                self.addCleanup(self.srv.terminate)
                self.srv.udp_thread.join(5)
                self.assertFalse(self.srv.udp_thread.is_alive())
                mock_socket.assert_called_with(socket.AF_INET6,
                                               socket.SOCK_DGRAM)

    def test_udp_receive_storage_error(self):
        self._setup_messaging(False)
        mock_record = self.mock_dispatcher.record_metering_data
        mock_record.side_effect = self._raise_error

        udp_socket = self._make_fake_socket(self.sample)
        with mock.patch('select.select', return_value=([udp_socket], [], [])):
            with mock.patch('socket.socket', return_value=udp_socket):
                self.srv.run()
                self.addCleanup(self.srv.terminate)
                self.srv.udp_thread.join(5)
                self.assertFalse(self.srv.udp_thread.is_alive())

        self._verify_udp_socket(udp_socket)

        mock_record.assert_called_once_with(self.sample)

    @staticmethod
    def _raise_error(*args, **kwargs):
        raise Exception

    @mock.patch.object(collector, 'LOG')
    def test_udp_receive_bad_decoding(self, log):
        self._setup_messaging(False)
        udp_socket = self._make_fake_socket(self.sample)
        with mock.patch('select.select', return_value=([udp_socket], [], [])):
            with mock.patch('socket.socket', return_value=udp_socket):
                with mock.patch('msgpack.loads', self._raise_error):
                    self.srv.run()
                    self.addCleanup(self.srv.terminate)
                    self.srv.udp_thread.join(5)
                    self.assertFalse(self.srv.udp_thread.is_alive())

        self._verify_udp_socket(udp_socket)
        log.warning.assert_called_once_with(
            "UDP: Cannot decode data sent by %s", mock.ANY)

    @mock.patch.object(collector.CollectorService, 'start_udp')
    def test_only_udp(self, udp_start):
        """Check that only UDP is started if messaging transport is unset."""
        self._setup_messaging(False)
        udp_socket = self._make_fake_socket(self.sample)
        real_start = oslo_messaging.MessageHandlingServer.start
        with mock.patch.object(oslo_messaging.MessageHandlingServer,
                               'start', side_effect=real_start) as rpc_start:
            with mock.patch('socket.socket', return_value=udp_socket):
                self.srv.run()
                self.addCleanup(self.srv.terminate)
                self.srv.udp_thread.join(5)
                self.assertFalse(self.srv.udp_thread.is_alive())
                self.assertEqual(0, rpc_start.call_count)
                self.assertEqual(1, udp_start.call_count)

    def test_udp_receive_valid_encoding(self):
        self._setup_messaging(False)
        self.data_sent = []
        sock = self._make_fake_socket(self.utf8_msg)
        with mock.patch('select.select', return_value=([sock], [], [])):
            with mock.patch('socket.socket', return_value=sock):
                self.srv.run()
                self.addCleanup(self.srv.terminate)
                self.srv.udp_thread.join(5)
                self.assertFalse(self.srv.udp_thread.is_alive())
                self.assertTrue(utils.verify_signature(
                    self.mock_dispatcher.method_calls[0][1][0],
                    "not-so-secret"))

    def _test_collector_requeue(self, listener, batch_listener=False):

        self.srv.dispatcher_manager = dispatcher.load_dispatcher_manager()
        mock_record = self.mock_dispatcher.record_metering_data
        mock_record.side_effect = Exception('boom')
        self.mock_dispatcher.record_events.side_effect = Exception('boom')

        self.srv.run()
        self.addCleanup(self.srv.terminate)
        endp = getattr(self.srv, listener).dispatcher.endpoints[0]
        ret = endp.sample([{'ctxt': {}, 'publisher_id': 'pub_id',
                            'event_type': 'event', 'payload': {},
                            'metadata': {}}])
        self.assertEqual(oslo_messaging.NotificationResult.REQUEUE,
                         ret)

    @mock.patch.object(collector.CollectorService, 'start_udp', mock.Mock())
    def test_collector_sample_requeue(self):
        self._test_collector_requeue('sample_listener')

    @mock.patch.object(collector.CollectorService, 'start_udp', mock.Mock())
    def test_collector_event_requeue(self):
        self._test_collector_requeue('event_listener')
