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

import datetime

from ceilometer import meter
from ceilometer.collector import manager
from ceilometer.storage import base
from ceilometer.tests import base as tests_base


class TestCollectorManager(tests_base.TestCase):

    def setUp(self):
        super(TestCollectorManager, self).setUp()
        self.mgr = manager.CollectorManager()
        self.ctx = None

    def test_valid_message(self):
        msg = {'counter_name': 'test',
               'resource_id': self.id(),
               'counter_volume': 1,
               }
        msg['message_signature'] = meter.compute_signature(msg)

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
        msg['message_signature'] = meter.compute_signature(msg)

        expected = {}
        expected.update(msg)
        expected['timestamp'] = datetime.datetime(2012, 7, 2, 13, 53, 40)

        self.mgr.storage_conn = self.mox.CreateMock(base.Connection)
        self.mgr.storage_conn.record_metering_data(expected)
        self.mox.ReplayAll()

        self.mgr.record_metering_data(self.ctx, msg)
        self.mox.VerifyAll()
