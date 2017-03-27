#
# Copyright 2013 IBM Corp
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
from oslotest import base

from ceilometer.dispatcher import database
from ceilometer.publisher import utils
from ceilometer import service


class TestDispatcherDB(base.BaseTestCase):

    def setUp(self):
        super(TestDispatcherDB, self).setUp()
        self.CONF = service.prepare_service([], [])
        self.CONF.set_override('connection', 'sqlite://', group='database')
        self.meter_dispatcher = database.MeterDatabaseDispatcher(self.CONF)

    def test_valid_message(self):
        msg = {'counter_name': 'test',
               'resource_id': self.id(),
               'counter_volume': 1,
               }
        msg['message_signature'] = utils.compute_signature(
            msg, self.CONF.publisher.telemetry_secret,
        )

        with mock.patch.object(self.meter_dispatcher.conn,
                               'record_metering_data') as record_metering_data:
            self.meter_dispatcher.record_metering_data(msg)

        record_metering_data.assert_called_once_with(msg)

    def test_timestamp_conversion(self):
        msg = {'counter_name': 'test',
               'resource_id': self.id(),
               'counter_volume': 1,
               'timestamp': '2012-07-02T13:53:40Z',
               }
        msg['message_signature'] = utils.compute_signature(
            msg, self.CONF.publisher.telemetry_secret,
        )

        expected = msg.copy()
        expected['timestamp'] = datetime.datetime(2012, 7, 2, 13, 53, 40)

        with mock.patch.object(self.meter_dispatcher.conn,
                               'record_metering_data') as record_metering_data:
            self.meter_dispatcher.record_metering_data(msg)

        record_metering_data.assert_called_once_with(expected)

    def test_timestamp_tzinfo_conversion(self):
        msg = {'counter_name': 'test',
               'resource_id': self.id(),
               'counter_volume': 1,
               'timestamp': '2012-09-30T15:31:50.262-08:00',
               }
        msg['message_signature'] = utils.compute_signature(
            msg, self.CONF.publisher.telemetry_secret,
        )

        expected = msg.copy()
        expected['timestamp'] = datetime.datetime(2012, 9, 30, 23,
                                                  31, 50, 262000)

        with mock.patch.object(self.meter_dispatcher.conn,
                               'record_metering_data') as record_metering_data:
            self.meter_dispatcher.record_metering_data(msg)

        record_metering_data.assert_called_once_with(expected)
