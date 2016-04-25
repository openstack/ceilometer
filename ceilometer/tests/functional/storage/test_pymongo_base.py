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
"""Tests the mongodb functionality
"""

import copy
import datetime

import mock

from ceilometer.publisher import utils
from ceilometer import sample
from ceilometer.tests import db as tests_db
from ceilometer.tests.functional.storage import test_storage_scenarios


@tests_db.run_with('mongodb')
class CompatibilityTest(test_storage_scenarios.DBTestBase):

    def prepare_data(self):
        def old_record_metering_data(self, data):
            received_timestamp = datetime.datetime.utcnow()
            self.db.resource.update(
                {'_id': data['resource_id']},
                {'$set': {'project_id': data['project_id'],
                          'user_id': data['user_id'],
                          # Current metadata being used and when it was
                          # last updated.
                          'timestamp': data['timestamp'],
                          'received_timestamp': received_timestamp,
                          'metadata': data['resource_metadata'],
                          'source': data['source'],
                          },
                 '$addToSet': {'meter': {'counter_name': data['counter_name'],
                                         'counter_type': data['counter_type'],
                                         },
                               },
                 },
                upsert=True,
            )

            record = copy.copy(data)
            self.db.meter.insert(record)

        # Stubout with the old version DB schema, the one w/o 'counter_unit'
        with mock.patch.object(self.conn, 'record_metering_data',
                               side_effect=old_record_metering_data):
            self.counters = []
            c = sample.Sample(
                'volume.size',
                'gauge',
                'GiB',
                5,
                'user-id',
                'project1',
                'resource-id',
                timestamp=datetime.datetime(2012, 9, 25, 10, 30),
                resource_metadata={'display_name': 'test-volume',
                                   'tag': 'self.counter',
                                   },
                source='test',
            )
            self.counters.append(c)
            msg = utils.meter_message_from_counter(
                c,
                secret='not-so-secret')
            self.conn.record_metering_data(self.conn, msg)

    def test_counter_unit(self):
        meters = list(self.conn.get_meters())
        self.assertEqual(1, len(meters))


@tests_db.run_with('mongodb')
class FilterQueryTestForMeters(test_storage_scenarios.DBTestBase):
    def prepare_data(self):
        def old_record_metering_data(self, data):
            received_timestamp = datetime.datetime.utcnow()
            self.db.resource.update(
                {'_id': data['resource_id']},
                {'$set': {'project_id': data['project_id'],
                          'user_id': data['user_id'],
                          # Current metadata being used and when it was
                          # last updated.
                          'timestamp': data['timestamp'],
                          'received_timestamp': received_timestamp,
                          'metadata': data['resource_metadata'],
                          'source': data['source'],
                          },
                 '$addToSet': {'meter': {'counter_name': data['counter_name'],
                                         'counter_type': data['counter_type'],
                                         },
                               },
                 },
                upsert=True,
            )

            record = copy.copy(data)
            self.db.meter.insert(record)

        # Stubout with the old version DB schema, the one w/o 'counter_unit'
        with mock.patch.object(self.conn, 'record_metering_data',
                               side_effect=old_record_metering_data):
            self.counters = []
            c = sample.Sample(
                'volume.size',
                'gauge',
                'GiB',
                5,
                None,
                None,
                None,
                timestamp=datetime.datetime(2012, 9, 25, 10, 30),
                resource_metadata={'display_name': 'test-volume',
                                   'tag': 'self.counter',
                                   },
                source='test',
            )

            self.counters.append(c)
            msg = utils.meter_message_from_counter(
                c,
                secret='not-so-secret')
            self.conn.record_metering_data(self.conn, msg)

    def test_get_meters_by_user(self):
        meters = list(self.conn.get_meters(user='None'))
        self.assertEqual(1, len(meters))

    def test_get_meters_by_resource(self):
        meters = list(self.conn.get_meters(resource='None'))
        self.assertEqual(1, len(meters))

    def test_get_meters_by_project(self):
        meters = list(self.conn.get_meters(project='None'))
        self.assertEqual(1, len(meters))
