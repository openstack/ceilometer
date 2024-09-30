#
# Copyright 2024 Red Hat, Inc
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

"""Tests for ceilometer polling heartbeat process"""

import multiprocessing
import shutil
import tempfile

from oslo_utils import timeutils
from unittest import mock

from ceilometer.polling import manager
from ceilometer import service
from ceilometer.tests import base


class TestHeartBeatManagert(base.BaseTestCase):
    def setUp(self):
        super(TestHeartBeatManagert, self).setUp()
        self.conf = service.prepare_service([], [])
        self.tmpdir = tempfile.mkdtemp()

        self.queue = multiprocessing.Queue()
        self.mgr = manager.AgentManager(0, self.conf, namespaces='central',
                                        queue=self.queue)

    def tearDown(self):
        super(TestHeartBeatManagert, self).tearDown()
        shutil.rmtree(self.tmpdir)

    def setup_polling(self, poll_cfg=None):
        name = self.cfg2file(poll_cfg or self.polling_cfg)
        self.conf.set_override('cfg_file', name, group='polling')
        self.mgr.polling_manager = manager.PollingManager(self.conf)

    def test_hb_not_configured(self):
        self.assertRaises(manager.HeartBeatException,
                          manager.AgentHeartBeatManager,
                          0, self.conf,
                          namespaces='ipmi',
                          queue=self.queue)

    @mock.patch('ceilometer.polling.manager.LOG')
    def test_hb_startup(self, LOG):
        # activate heartbeat agent
        self.conf.set_override('heartbeat_socket_dir', self.tmpdir,
                               group='polling')
        manager.AgentHeartBeatManager(0, self.conf, namespaces='compute',
                                      queue=self.queue)
        calls = [mock.call("Starting heartbeat child service. Listening"
                           f" on {self.tmpdir}/ceilometer-compute.socket")]
        LOG.info.assert_has_calls(calls)

    @mock.patch('ceilometer.polling.manager.LOG')
    def test_hb_update(self, LOG):
        self.conf.set_override('heartbeat_socket_dir', self.tmpdir,
                               group='polling')
        hb = manager.AgentHeartBeatManager(0, self.conf, namespaces='central',
                                           queue=self.queue)

        timestamp = timeutils.utcnow().isoformat()
        self.queue.put_nowait({'timestamp': timestamp, 'pollster': 'test'})

        hb._update_status()
        calls = [mock.call(f"Updated heartbeat for test ({timestamp})")]
        LOG.debug.assert_has_calls(calls)

    @mock.patch('ceilometer.polling.manager.LOG')
    def test_hb_send(self, LOG):
        with mock.patch('socket.socket') as FakeSocket:
            sub_skt = mock.Mock()
            sub_skt.sendall.return_value = None
            sub_skt.sendall.return_value = None

            skt = FakeSocket.return_value
            skt.bind.return_value = mock.Mock()
            skt.listen.return_value = mock.Mock()
            skt.accept.return_value = (sub_skt, "")

            self.conf.set_override('heartbeat_socket_dir', self.tmpdir,
                                   group='polling')
            hb = manager.AgentHeartBeatManager(0, self.conf,
                                               namespaces='central',
                                               queue=self.queue)
            timestamp = timeutils.utcnow().isoformat()
            self.queue.put_nowait({'timestamp': timestamp,
                                   'pollster': 'test1'})
            hb._update_status()
            self.queue.put_nowait({'timestamp': timestamp,
                                   'pollster': 'test2'})
            hb._update_status()

            # test status report
            hb._send_heartbeat()
            calls = [mock.call("Heartbeat status report requested "
                               f"at {self.tmpdir}/ceilometer-central.socket"),
                     mock.call("Reported heartbeat status:\n"
                               f"test1 {timestamp}\n"
                               f"test2 {timestamp}")]
            LOG.debug.assert_has_calls(calls)
