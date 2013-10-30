# -*- encoding: utf-8 -*-
#
# Copyright © 2013 IBM Corp
#
# Author: Tong Li <litong01@us.ibm.com>
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
"""Tests for ceilometer/collector/dispatcher/database.py
"""
from datetime import datetime

from ceilometer.collector.dispatcher import database
from ceilometer.openstack.common.fixture import config
from ceilometer.openstack.common.fixture import moxstubout
from ceilometer.openstack.common import test
from ceilometer.publisher import rpc
from ceilometer.storage import base


class TestDispatcherDB(test.BaseTestCase):

    def setUp(self):
        super(TestDispatcherDB, self).setUp()
        self.CONF = self.useFixture(config.Config()).conf
        self.dispatcher = database.DatabaseDispatcher(self.CONF)
        self.ctx = None
        self.mox = self.useFixture(moxstubout.MoxStubout()).mox

    def test_valid_message(self):
        msg = {'counter_name': 'test',
               'resource_id': self.id(),
               'counter_volume': 1,
               }
        msg['message_signature'] = rpc.compute_signature(
            msg,
            self.CONF.publisher_rpc.metering_secret,
        )

        self.dispatcher.storage_conn = self.mox.CreateMock(base.Connection)
        self.dispatcher.storage_conn.record_metering_data(msg)
        self.mox.ReplayAll()

        self.dispatcher.record_metering_data(self.ctx, msg)
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

        self.dispatcher.storage_conn = ErrorConnection()

        self.dispatcher.record_metering_data(self.ctx, msg)

        assert not self.dispatcher.storage_conn.called, \
            'Should not have called the storage connection'

    def test_timestamp_conversion(self):
        msg = {'counter_name': 'test',
               'resource_id': self.id(),
               'counter_volume': 1,
               'timestamp': '2012-07-02T13:53:40Z',
               }
        msg['message_signature'] = rpc.compute_signature(
            msg,
            self.CONF.publisher_rpc.metering_secret,
        )

        expected = {}
        expected.update(msg)
        expected['timestamp'] = datetime(2012, 7, 2, 13, 53, 40)

        self.dispatcher.storage_conn = self.mox.CreateMock(base.Connection)
        self.dispatcher.storage_conn.record_metering_data(expected)
        self.mox.ReplayAll()

        self.dispatcher.record_metering_data(self.ctx, msg)

    def test_timestamp_tzinfo_conversion(self):
        msg = {'counter_name': 'test',
               'resource_id': self.id(),
               'counter_volume': 1,
               'timestamp': '2012-09-30T15:31:50.262-08:00',
               }
        msg['message_signature'] = rpc.compute_signature(
            msg,
            self.CONF.publisher_rpc.metering_secret,
        )

        expected = {}
        expected.update(msg)
        expected['timestamp'] = datetime(2012, 9, 30, 23, 31, 50, 262000)

        self.dispatcher.storage_conn = self.mox.CreateMock(base.Connection)
        self.dispatcher.storage_conn.record_metering_data(expected)
        self.mox.ReplayAll()

        self.dispatcher.record_metering_data(self.ctx, msg)
