#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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

from ceilometer.alarm.storage import impl_mongodb as impl_mongodb_alarm
from ceilometer.storage import base
from ceilometer.storage import impl_mongodb
from ceilometer.tests import base as test_base
from ceilometer.tests import db as tests_db
from ceilometer.tests.storage import test_storage_scenarios


@tests_db.run_with('mongodb')
class MongoDBConnection(tests_db.TestBase):
    def test_connection_pooling(self):
        test_conn = impl_mongodb.Connection(self.db_manager.url)
        self.assertEqual(self.conn.conn, test_conn.conn)

    def test_replica_set(self):
        url = self.db_manager._url + '?replicaSet=foobar'
        conn = impl_mongodb.Connection(url)
        self.assertTrue(conn.conn)

    def test_recurse_sort_keys(self):
        sort_keys = ['k1', 'k2', 'k3']
        marker = {'k1': 'v1', 'k2': 'v2', 'k3': 'v3'}
        flag = '$lt'
        ret = impl_mongodb.Connection._recurse_sort_keys(sort_keys=sort_keys,
                                                         marker=marker,
                                                         flag=flag)
        expect = {'k3': {'$lt': 'v3'}, 'k2': {'eq': 'v2'}, 'k1': {'eq': 'v1'}}
        self.assertEqual(expect, ret)


@tests_db.run_with('mongodb')
class MongoDBTestMarkerBase(test_storage_scenarios.DBTestBase):
    # NOTE(Fengqian): All these three test case are the same for resource
    # and meter collection. As to alarm, we will set up in AlarmTestPagination.
    def test_get_marker(self):
        marker_pairs = {'user_id': 'user-id-4'}
        ret = impl_mongodb.Connection._get_marker(self.conn.db.resource,
                                                  marker_pairs)
        self.assertEqual('project-id-4', ret['project_id'])

    def test_get_marker_None(self):
        marker_pairs = {'user_id': 'user-id-foo'}
        try:
            ret = impl_mongodb.Connection._get_marker(self.conn.db.resource,
                                                      marker_pairs)
            self.assertEqual('project-id-foo', ret['project_id'])
        except base.NoResultFound:
            self.assertTrue(True)

    def test_get_marker_multiple(self):
        try:
            marker_pairs = {'project_id': 'project-id'}
            ret = impl_mongodb.Connection._get_marker(self.conn.db.resource,
                                                      marker_pairs)
            self.assertEqual('project-id-foo', ret['project_id'])
        except base.MultipleResultsFound:
            self.assertTrue(True)


@tests_db.run_with('mongodb')
class IndexTest(tests_db.TestBase):
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
        self.assertEqual(456789,
                         self.conn.db.meter.index_information()
                         ['meter_ttl']['expireAfterSeconds'])

        self.CONF.set_override('time_to_live', -1, group='database')
        self.conn.upgrade()
        self.assertTrue(self.conn.db.meter.ensure_index('foo',
                                                        name='meter_ttl'))


@tests_db.run_with('mongodb')
class AlarmTestPagination(test_storage_scenarios.AlarmTestBase):
    def test_alarm_get_marker(self):
        self.add_some_alarms()
        marker_pairs = {'name': 'red-alert'}
        ret = impl_mongodb.Connection._get_marker(self.alarm_conn.db.alarm,
                                                  marker_pairs=marker_pairs)
        self.assertEqual('test.one', ret['rule']['meter_name'])

    def test_alarm_get_marker_None(self):
        self.add_some_alarms()
        try:
            marker_pairs = {'name': 'user-id-foo'}
            ret = impl_mongodb.Connection._get_marker(self.alarm_conn.db.alarm,
                                                      marker_pairs)
            self.assertEqual('meter_name-foo', ret['rule']['meter_name'])
        except base.NoResultFound:
            self.assertTrue(True)

    def test_alarm_get_marker_multiple(self):
        self.add_some_alarms()
        try:
            marker_pairs = {'user_id': 'me'}
            ret = impl_mongodb.Connection._get_marker(self.alarm_conn.db.alarm,
                                                      marker_pairs)
            self.assertEqual('counter-name-foo', ret['rule']['meter_name'])
        except base.MultipleResultsFound:
            self.assertTrue(True)


class CapabilitiesTest(test_base.BaseTestCase):
    # Check the returned capabilities list, which is specific to each DB
    # driver

    def test_capabilities(self):
        expected_capabilities = {
            'meters': {'pagination': False,
                       'query': {'simple': True,
                                 'metadata': True,
                                 'complex': False}},
            'resources': {'pagination': False,
                          'query': {'simple': True,
                                    'metadata': True,
                                    'complex': False}},
            'samples': {'pagination': False,
                        'groupby': False,
                        'query': {'simple': True,
                                  'metadata': True,
                                  'complex': True}},
            'statistics': {'pagination': False,
                           'groupby': True,
                           'query': {'simple': True,
                                     'metadata': True,
                                     'complex': False},
                           'aggregation': {'standard': True,
                                           'selectable': {
                                               'max': True,
                                               'min': True,
                                               'sum': True,
                                               'avg': True,
                                               'count': True,
                                               'stddev': True,
                                               'cardinality': True}}
                           },
            'events': {'query': {'simple': True}}
        }

        actual_capabilities = impl_mongodb.Connection.get_capabilities()
        self.assertEqual(expected_capabilities, actual_capabilities)

    def test_alarm_capabilities(self):
        expected_capabilities = {
            'alarms': {'query': {'simple': True,
                                 'complex': True},
                       'history': {'query': {'simple': True,
                                             'complex': True}}},
        }

        actual_capabilities = impl_mongodb_alarm.Connection.get_capabilities()
        self.assertEqual(expected_capabilities, actual_capabilities)

    def test_storage_capabilities(self):
        expected_capabilities = {
            'storage': {'production_ready': True},
        }
        actual_capabilities = (impl_mongodb.Connection.
                               get_storage_capabilities())
        self.assertEqual(expected_capabilities, actual_capabilities)
