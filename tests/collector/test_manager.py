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
"""Tests for ceilometer/agent/manager.py
"""

from datetime import datetime

from ceilometer import meter
from ceilometer.collector import manager
from ceilometer.openstack.common import cfg
from ceilometer.storage import base
from ceilometer.openstack.common import rpc
from ceilometer.openstack.common import cfg
from ceilometer.tests import base as tests_base
from ceilometer.compute import notifications


TEST_NOTICE = {
    u'_context_auth_token': u'3d8b13de1b7d499587dfc69b77dc09c2',
    u'_context_is_admin': True,
    u'_context_project_id': u'7c150a59fe714e6f9263774af9688f0e',
    u'_context_quota_class': None,
    u'_context_read_deleted': u'no',
    u'_context_remote_address': u'10.0.2.15',
    u'_context_request_id': u'req-d68b36e0-9233-467f-9afb-d81435d64d66',
    u'_context_roles': [u'admin'],
    u'_context_timestamp': u'2012-05-08T20:23:41.425105',
    u'_context_user_id': u'1e3ce043029547f1a61c1996d1a531a2',
    u'event_type': u'compute.instance.create.end',
    u'message_id': u'dae6f69c-00e0-41c0-b371-41ec3b7f4451',
    u'payload': {u'created_at': u'2012-05-08 20:23:41',
                 u'deleted_at': u'',
                 u'disk_gb': 0,
                 u'display_name': u'testme',
                 u'fixed_ips': [{u'address': u'10.0.0.2',
                                 u'floating_ips': [],
                                 u'meta': {},
                                 u'type': u'fixed',
                                 u'version': 4}],
                 u'image_ref_url': u'http://10.0.2.15:9292/images/UUID',
                 u'instance_id': u'9f9d01b9-4a58-4271-9e27-398b21ab20d1',
                 u'instance_type': u'm1.tiny',
                 u'instance_type_id': 2,
                 u'launched_at': u'2012-05-08 20:23:47.985999',
                 u'memory_mb': 512,
                 u'state': u'active',
                 u'state_description': u'',
                 u'tenant_id': u'7c150a59fe714e6f9263774af9688f0e',
                 u'user_id': u'1e3ce043029547f1a61c1996d1a531a2',
                 u'reservation_id': u'1e3ce043029547f1a61c1996d1a531a3',
                 u'vcpus': 1,
                 u'root_gb': 0,
                 u'ephemeral_gb': 0,
                 u'host': u'compute-host-name',
                 u'availability_zone': u'1e3ce043029547f1a61c1996d1a531a4',
                 u'os_type': u'linux?',
                 u'architecture': u'x86',
                 u'image_ref': u'UUID',
                 u'kernel_id': u'1e3ce043029547f1a61c1996d1a531a5',
                 u'ramdisk_id': u'1e3ce043029547f1a61c1996d1a531a6',
                 },
    u'priority': u'INFO',
    u'publisher_id': u'compute.vagrant-precise',
    u'timestamp': u'2012-05-08 20:23:48.028195',
    }


class StubConnection(object):
    def declare_topic_consumer(*args, **kwargs):
        pass

    def create_worker(*args, **kwargs):
        pass

    def consume_in_thread(self):
        pass


class TestCollectorManager(tests_base.TestCase):

    def setUp(self):
        super(TestCollectorManager, self).setUp()
        self.mgr = manager.CollectorManager()
        self.ctx = None
        #cfg.CONF.metering_secret = 'not-so-secret'

    def test_init_host(self):
        self.stubs.Set(rpc, 'create_connection', lambda: StubConnection())
        cfg.CONF.database_connection = 'log://localhost'
        self.mgr.init_host()

    def test_valid_message(self):
        msg = {'counter_name': 'test',
               'resource_id': self.id(),
               'counter_volume': 1,
               }
        msg['message_signature'] = meter.compute_signature(
            msg,
            cfg.CONF.metering_secret,
            )

        self.mgr.storage_conn = self.mox.CreateMock(base.Connection)
        self.mgr.storage_conn.record_metering_data(msg)
        self.mox.ReplayAll()

        self.mgr.record_metering_data(self.ctx, msg)
        self.mox.VerifyAll()

    def test_invalid_message(self):
        msg = {'counter_name': 'test',
               'resource_id': self.id(),
               'counter_volume': 1,
               }
        msg['message_signature'] = 'invalid-signature'

        class ErrorConnection:

            called = False

            def record_metering_data(self, data):
                self.called = True

        self.mgr.storage_conn = ErrorConnection()

        self.mgr.record_metering_data(self.ctx, msg)

        assert not self.mgr.storage_conn.called, \
            'Should not have called the storage connection'

    def test_timestamp_conversion(self):
        msg = {'counter_name': 'test',
               'resource_id': self.id(),
               'counter_volume': 1,
               'timestamp': '2012-07-02T13:53:40Z',
               }
        msg['message_signature'] = meter.compute_signature(
            msg,
            cfg.CONF.metering_secret,
            )

        expected = {}
        expected.update(msg)
        expected['timestamp'] = datetime(2012, 7, 2, 13, 53, 40)

        self.mgr.storage_conn = self.mox.CreateMock(base.Connection)
        self.mgr.storage_conn.record_metering_data(expected)
        self.mox.ReplayAll()

        self.mgr.record_metering_data(self.ctx, msg)
        self.mox.VerifyAll()

    def test_timestamp_tzinfo_conversion(self):
        msg = {'counter_name': 'test',
               'resource_id': self.id(),
               'counter_volume': 1,
               'timestamp': '2012-09-30T15:31:50.262-08:00',
               }
        msg['message_signature'] = meter.compute_signature(
            msg,
            cfg.CONF.metering_secret,
            )

        expected = {}
        expected.update(msg)
        expected['timestamp'] = datetime(2012, 9, 30, 23, 31, 50, 262000)

        self.mgr.storage_conn = self.mox.CreateMock(base.Connection)
        self.mgr.storage_conn.record_metering_data(expected)
        self.mox.ReplayAll()

        self.mgr.record_metering_data(self.ctx, msg)
        self.mox.VerifyAll()

    def test_load_plugins(self):
        results = self.mgr._load_plugins(self.mgr.COLLECTOR_NAMESPACE)
        self.assert_(len(results) > 0)

    def test_load_no_plugins(self):
        results = self.mgr._load_plugins("foobar.namespace")
        self.assertEqual(results, [])

    def test_process_notification(self):
        results = []
        self.stubs.Set(self.mgr, 'publish_counter',
                       lambda counter: results.append(counter))
        self.mgr.handlers = [notifications.Instance()]
        self.mgr.process_notification(TEST_NOTICE)
        self.assert_(len(results) >= 1)
