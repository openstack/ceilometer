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
import datetime

import mock

from ceilometer.dispatcher import database
from ceilometer.openstack.common.fixture import config
from ceilometer.openstack.common import test
from ceilometer.publisher import utils


class TestDispatcherDB(test.BaseTestCase):

    def setUp(self):
        super(TestDispatcherDB, self).setUp()
        self.CONF = self.useFixture(config.Config()).conf
        self.dispatcher = database.DatabaseDispatcher(self.CONF)
        self.ctx = None

    def test_valid_message(self):
        msg = {'counter_name': 'test',
               'resource_id': self.id(),
               'counter_volume': 1,
               }
        msg['message_signature'] = utils.compute_signature(
            msg,
            self.CONF.publisher.metering_secret,
        )

        with mock.patch.object(self.dispatcher.storage_conn,
                               'record_metering_data') as record_metering_data:
            self.dispatcher.record_metering_data(msg)

        record_metering_data.assert_called_once_with(msg)

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

        self.dispatcher.record_metering_data(msg)

        assert not self.dispatcher.storage_conn.called, \
            'Should not have called the storage connection'

    def test_timestamp_conversion(self):
        msg = {'counter_name': 'test',
               'resource_id': self.id(),
               'counter_volume': 1,
               'timestamp': '2012-07-02T13:53:40Z',
               }
        msg['message_signature'] = utils.compute_signature(
            msg,
            self.CONF.publisher.metering_secret,
        )

        expected = msg.copy()
        expected['timestamp'] = datetime.datetime(2012, 7, 2, 13, 53, 40)

        with mock.patch.object(self.dispatcher.storage_conn,
                               'record_metering_data') as record_metering_data:
            self.dispatcher.record_metering_data(msg)

        record_metering_data.assert_called_once_with(expected)

    def test_timestamp_tzinfo_conversion(self):
        msg = {'counter_name': 'test',
               'resource_id': self.id(),
               'counter_volume': 1,
               'timestamp': '2012-09-30T15:31:50.262-08:00',
               }
        msg['message_signature'] = utils.compute_signature(
            msg,
            self.CONF.publisher.metering_secret,
        )

        expected = msg.copy()
        expected['timestamp'] = datetime.datetime(2012, 9, 30, 23,
                                                  31, 50, 262000)

        with mock.patch.object(self.dispatcher.storage_conn,
                               'record_metering_data') as record_metering_data:
            self.dispatcher.record_metering_data(msg)

        record_metering_data.assert_called_once_with(expected)
