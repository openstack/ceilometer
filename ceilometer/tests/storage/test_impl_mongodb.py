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
"""Tests for ceilometer/storage/impl_mongodb.py

.. note::
  In order to run the tests against another MongoDB server set the
  environment variable CEILOMETER_TEST_MONGODB_URL to point to a MongoDB
  server before running the tests.

"""

import copy
import datetime
from mock import patch

from ceilometer.publisher import utils
from ceilometer import sample
from ceilometer.storage import base
from ceilometer.storage import impl_mongodb
from ceilometer.tests import db as tests_db
from ceilometer.tests.storage import test_storage_scenarios


class MongoDBEngineTestBase(tests_db.TestBase):
    database_connection = tests_db.MongoDBFakeConnectionUrl()


class MongoDBConnection(MongoDBEngineTestBase):
    def test_connection_pooling(self):
        self.assertEqual(self.conn.conn,
                         impl_mongodb.Connection(self.CONF).conn)

    def test_replica_set(self):
        self.CONF.set_override(
            'connection',
            str(tests_db.MongoDBFakeConnectionUrl()) + '?replicaSet=foobar',
            group='database')
        conn = impl_mongodb.Connection(self.CONF)
        self.assertTrue(conn.conn)

    def test_recurse_sort_keys(self):
        sort_keys = ['k1', 'k2', 'k3']
        marker = {'k1': 'v1', 'k2': 'v2', 'k3': 'v3'}
        flag = '$lt'
        ret = impl_mongodb.Connection._recurse_sort_keys(sort_keys=sort_keys,
                                                         marker=marker,
                                                         flag=flag)
        expect = {'k3': {'$lt': 'v3'}, 'k2': {'eq': 'v2'}, 'k1': {'eq': 'v1'}}
        self.assertEqual(ret, expect)


class MongoDBTestMarkerBase(test_storage_scenarios.DBTestBase,
                            MongoDBEngineTestBase):
    #NOTE(Fengqian): All these three test case are the same for resource
    #and meter collection. As to alarm, we will set up in AlarmTestPagination.
    def test_get_marker(self):
        marker_pairs = {'user_id': 'user-id-4'}
        ret = impl_mongodb.Connection._get_marker(self.conn.db.resource,
                                                  marker_pairs)
        self.assertEqual(ret['project_id'], 'project-id-4')

    def test_get_marker_None(self):
        marker_pairs = {'user_id': 'user-id-foo'}
        try:
            ret = impl_mongodb.Connection._get_marker(self.conn.db.resource,
                                                      marker_pairs)
            self.assertEqual(ret['project_id'], 'project-id-foo')
        except base.NoResultFound:
            self.assertTrue(True)

    def test_get_marker_multiple(self):
        try:
            marker_pairs = {'project_id': 'project-id'}
            ret = impl_mongodb.Connection._get_marker(self.conn.db.resource,
                                                      marker_pairs)
            self.assertEqual(ret['project_id'], 'project-id-foo')
        except base.MultipleResultsFound:
            self.assertTrue(True)


class IndexTest(MongoDBEngineTestBase):
    def test_meter_ttl_index_absent(self):
        # create a fake index and check it is deleted
        self.conn.db.meter.ensure_index('foo', name='meter_ttl')
        self.CONF.set_override('time_to_live', -1, group='database')
        self.conn.upgrade()
        self.assertTrue(self.conn.db.meter.ensure_index('foo',
                                                        name='meter_ttl'))
        self.CONF.set_override('time_to_live', 456789, group='database')
        self.conn.upgrade()
        self.assertFalse(self.conn.db.meter.ensure_index('foo',
                                                         name='meter_ttl'))

    def test_meter_ttl_index_present(self):
        self.CONF.set_override('time_to_live', 456789, group='database')
        self.conn.upgrade()
        self.assertFalse(self.conn.db.meter.ensure_index('foo',
                                                         name='meter_ttl'))
        self.assertEqual(self.conn.db.meter.index_information()[
            'meter_ttl']['expireAfterSeconds'], 456789)

        self.CONF.set_override('time_to_live', -1, group='database')
        self.conn.upgrade()
        self.assertTrue(self.conn.db.meter.ensure_index('foo',
                                                        name='meter_ttl'))


class CompatibilityTest(test_storage_scenarios.DBTestBase,
                        MongoDBEngineTestBase):
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
        self.assertEqual(old.type, 'threshold')
        self.assertEqual(old.rule['query'],
                         [{'field': 'key',
                           'op': 'eq',
                           'value': 'value',
                           'type': 'string'}])
        self.assertEqual(old.rule['period'], 60)
        self.assertEqual(old.rule['meter_name'], 'cpu')
        self.assertEqual(old.rule['evaluation_periods'], 1)
        self.assertEqual(old.rule['statistic'], 'count')
        self.assertEqual(old.rule['comparison_operator'], 'lt')
        self.assertEqual(old.rule['threshold'], 36)

    def test_alarm_get_old_format_matching_metadata_array(self):
        old = list(self.conn.get_alarms(name='other-old-alaert'))[0]
        self.assertEqual(old.type, 'threshold')
        self.assertEqual(sorted(old.rule['query']),
                         sorted([{'field': 'key1',
                                  'op': 'eq',
                                  'value': 'value1',
                                  'type': 'string'},
                                 {'field': 'key2',
                                  'op': 'eq',
                                  'value': 'value2',
                                  'type': 'string'}]))
        self.assertEqual(old.rule['meter_name'], 'cpu')
        self.assertEqual(old.rule['period'], 60)
        self.assertEqual(old.rule['evaluation_periods'], 1)
        self.assertEqual(old.rule['statistic'], 'count')
        self.assertEqual(old.rule['comparison_operator'], 'lt')
        self.assertEqual(old.rule['threshold'], 36)

    def test_counter_unit(self):
        meters = list(self.conn.get_meters())
        self.assertEqual(len(meters), 1)


class AlarmTestPagination(test_storage_scenarios.AlarmTestBase,
                          MongoDBEngineTestBase):
    def test_alarm_get_marker(self):
        self.add_some_alarms()
        marker_pairs = {'name': 'red-alert'}
        ret = impl_mongodb.Connection._get_marker(self.conn.db.alarm,
                                                  marker_pairs=marker_pairs)
        self.assertEqual(ret['rule']['meter_name'], 'test.one')

    def test_alarm_get_marker_None(self):
        self.add_some_alarms()
        try:
            marker_pairs = {'name': 'user-id-foo'}
            ret = impl_mongodb.Connection._get_marker(self.conn.db.alarm,
                                                      marker_pairs)
            self.assertEqual(ret['rule']['meter_name'],
                             'meter_name-foo')
        except base.NoResultFound:
            self.assertTrue(True)

    def test_alarm_get_marker_multiple(self):
        self.add_some_alarms()
        try:
            marker_pairs = {'user_id': 'me'}
            ret = impl_mongodb.Connection._get_marker(self.conn.db.alarm,
                                                      marker_pairs)
            self.assertEqual(ret['rule']['meter_name'],
                             'counter-name-foo')
        except base.MultipleResultsFound:
            self.assertTrue(True)
