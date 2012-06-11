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

from nova import context
from nova import test

from ceilometer import meter
from ceilometer.collector import manager
from ceilometer.storage import base


class TestCollectorManager(test.TestCase):

    def setUp(self):
        super(TestCollectorManager, self).setUp()
        self.mgr = manager.CollectorManager()
        self.ctx = context.RequestContext("user", "project")

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
