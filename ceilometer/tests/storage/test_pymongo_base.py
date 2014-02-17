# -*- encoding: utf-8 -*-
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
"""Tests the mongodb and db2 common functionality
"""

import copy
import datetime

from mock import patch
import testscenarios

from ceilometer.publisher import utils
from ceilometer import sample
from ceilometer.tests import db as tests_db
from ceilometer.tests.storage import test_storage_scenarios

load_tests = testscenarios.load_tests_apply_scenarios


class CompatibilityTest(test_storage_scenarios.DBTestBase,
                        tests_db.MixinTestsWithBackendScenarios):

    scenarios = [
        ('mongodb',
         dict(database_connection=tests_db.MongoDBFakeConnectionUrl())),
        ('db2',
         dict(database_connection=tests_db.DB2FakeConnectionUrl())),
    ]

    def prepare_data(self):
        def old_record_metering_data(self, data):
            self.db.user.update(
                {'_id': data['user_id']},
                {'$addToSet': {'source': data['source'],
                               },
                 },
                upsert=True,
            )
            self.db.project.update(
                {'_id': data['project_id']},
                {'$addToSet': {'source': data['source'],
                               },
                 },
                upsert=True,
            )
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
        with patch.object(self.conn, 'record_metering_data',
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

        # Create the old format alarm with a dict instead of a
        # array for matching_metadata
        alarm = dict(alarm_id='0ld-4l3rt',
                     enabled=True,
                     name='old-alert',
                     description='old-alert',
                     timestamp=None,
                     meter_name='cpu',
                     user_id='me',
                     project_id='and-da-boys',
                     comparison_operator='lt',
                     threshold=36,
                     statistic='count',
                     evaluation_periods=1,
                     period=60,
                     state="insufficient data",
                     state_timestamp=None,
                     ok_actions=[],
                     alarm_actions=['http://nowhere/alarms'],
                     insufficient_data_actions=[],
                     repeat_actions=False,
                     matching_metadata={'key': 'value'})

        self.conn.db.alarm.update(
            {'alarm_id': alarm['alarm_id']},
            {'$set': alarm},
            upsert=True)

        alarm['alarm_id'] = 'other-kind-of-0ld-4l3rt'
        alarm['name'] = 'other-old-alaert'
        alarm['matching_metadata'] = [{'key': 'key1', 'value': 'value1'},
                                      {'key': 'key2', 'value': 'value2'}]
        self.conn.db.alarm.update(
            {'alarm_id': alarm['alarm_id']},
            {'$set': alarm},
            upsert=True)

    def test_alarm_get_old_format_matching_metadata_dict(self):
        old = list(self.conn.get_alarms(name='old-alert'))[0]
        self.assertEqual('threshold', old.type)
        self.assertEqual([{'field': 'key',
                           'op': 'eq',
                           'value': 'value',
                           'type': 'string'}],
                         old.rule['query'])
        self.assertEqual(60, old.rule['period'])
        self.assertEqual('cpu', old.rule['meter_name'])
        self.assertEqual(1, old.rule['evaluation_periods'])
        self.assertEqual('count', old.rule['statistic'])
        self.assertEqual('lt', old.rule['comparison_operator'])
        self.assertEqual(36, old.rule['threshold'])

    def test_alarm_get_old_format_matching_metadata_array(self):
        old = list(self.conn.get_alarms(name='other-old-alaert'))[0]
        self.assertEqual('threshold', old.type)
        self.assertEqual(sorted([{'field': 'key1',
                                  'op': 'eq',
                                  'value': 'value1',
                                  'type': 'string'},
                                 {'field': 'key2',
                                  'op': 'eq',
                                  'value': 'value2',
                                  'type': 'string'}]),
                         sorted(old.rule['query']),)
        self.assertEqual('cpu', old.rule['meter_name'])
        self.assertEqual(60, old.rule['period'])
        self.assertEqual(1, old.rule['evaluation_periods'])
        self.assertEqual('count', old.rule['statistic'])
        self.assertEqual('lt', old.rule['comparison_operator'])
        self.assertEqual(36, old.rule['threshold'])

    def test_counter_unit(self):
        meters = list(self.conn.get_meters())
        self.assertEqual(1, len(meters))
