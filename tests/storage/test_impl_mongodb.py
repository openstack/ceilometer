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
import uuid

from oslo.config import cfg

from tests.storage import base

from ceilometer.publisher import rpc
from ceilometer import sample
from ceilometer.storage import impl_mongodb
from ceilometer.storage import models
from ceilometer.tests import db as tests_db
from ceilometer.storage.base import NoResultFound
from ceilometer.storage.base import MultipleResultsFound


class MongoDBEngineTestBase(base.DBTestBase):
    database_connection = tests_db.MongoDBFakeConnectionUrl()


class MongoDBConnection(MongoDBEngineTestBase):
    def test_connection_pooling(self):
        self.assertEqual(self.conn.conn,
                         impl_mongodb.Connection(cfg.CONF).conn)

    def test_replica_set(self):
        cfg.CONF.set_override(
            'connection',
            str(tests_db.MongoDBFakeConnectionUrl()) + '?replicaSet=foobar',
            group='database')
        conn = impl_mongodb.Connection(cfg.CONF)
        self.assertTrue(conn.conn)

    def test_recurse_sort_keys(self):
        sort_keys = ['k1', 'k2', 'k3']
        marker = {'k1': 'v1', 'k2': 'v2', 'k3': 'v3'}
        flag = '$lt'
        ret = impl_mongodb.Connection._recurse_sort_keys(sort_keys=sort_keys,
                                                         marker=marker,
                                                         flag=flag)
        expect = {'k3': {'$lt': 'v3'}, 'k2': {'eq': 'v2'}, 'k1': {'eq': 'v1'}}
        self.assertEquals(ret, expect)


class MongoDBTestMarkerBase(MongoDBEngineTestBase):
    #NOTE(Fengqian): All these three test case are the same for resource
    #and meter collection. As to alarm, we will set up in AlarmTestPagination.
    def test_get_marker(self):
        marker_pairs = {'user_id': 'user-id-4'}
        ret = impl_mongodb.Connection._get_marker(self.conn.db.resource,
                                                  marker_pairs)
        self.assertEqual(ret['project_id'], 'project-id-4')

    def test_get_marker_None(self):
        try:
            marker_pairs = {'user_id': 'user-id-foo'}
            ret = impl_mongodb.Connection._get_marker(self.conn.db.resource,
                                                      marker_pairs)
            self.assertEqual(ret['project_id'], 'project-id-foo')
        except NoResultFound:
            self.assertTrue(True)

    def test_get_marker_multiple(self):
        try:
            marker_pairs = {'project_id': 'project-id'}
            ret = impl_mongodb.Connection._get_marker(self.conn.db.resource,
                                                      marker_pairs)
            self.assertEqual(ret['project_id'], 'project-id-foo')
        except MultipleResultsFound:
            self.assertTrue(True)


class IndexTest(MongoDBEngineTestBase):
    def test_meter_ttl_index_absent(self):
        # create a fake index and check it is deleted
        self.conn.db.meter.ensure_index('foo', name='meter_ttl')
        cfg.CONF.set_override('time_to_live', -1, group='database')

        self.conn._ensure_meter_ttl_index()
        self.assertTrue(self.conn.db.meter.ensure_index('foo',
                                                        name='meter_ttl'))
        cfg.CONF.set_override('time_to_live', 456789, group='database')
        self.conn._ensure_meter_ttl_index()
        self.assertFalse(self.conn.db.meter.ensure_index('foo',
                                                         name='meter_ttl'))

    def test_meter_ttl_index_present(self):
        cfg.CONF.set_override('time_to_live', 456789, group='database')
        self.conn._ensure_meter_ttl_index()
        self.assertFalse(self.conn.db.meter.ensure_index('foo',
                                                         name='meter_ttl'))
        self.assertEqual(self.conn.db.meter.index_information()[
            'meter_ttl']['expireAfterSeconds'], 456789)

        cfg.CONF.set_override('time_to_live', -1, group='database')
        self.conn._ensure_meter_ttl_index()
        self.assertTrue(self.conn.db.meter.ensure_index('foo',
                                                        name='meter_ttl'))

    def test_ttl_index_is_supported(self):
        self.mox.StubOutWithMock(self.conn.conn, "server_info")
        self.conn.conn.server_info().AndReturn({'versionArray': [2, 4, 5, 0]})

        self.mox.ReplayAll()
        self.assertTrue(self.conn._is_natively_ttl_supported())
        self.mox.UnsetStubs()
        self.mox.VerifyAll()

    def test_ttl_index_is_not_supported(self):
        self.mox.StubOutWithMock(self.conn.conn, "server_info")
        self.conn.conn.server_info().AndReturn({'versionArray': [2, 0, 1, 0]})

        self.mox.ReplayAll()
        self.assertFalse(self.conn._is_natively_ttl_supported())
        self.mox.UnsetStubs()
        self.mox.VerifyAll()

    def test_ttl_index_is_unkown(self):
        self.mox.StubOutWithMock(self.conn.conn, "server_info")
        self.conn.conn.server_info().AndReturn({})

        self.mox.ReplayAll()
        self.assertFalse(self.conn._is_natively_ttl_supported())
        self.mox.UnsetStubs()
        self.mox.VerifyAll()


class UserTest(base.UserTest, MongoDBEngineTestBase):
    pass


class ProjectTest(base.ProjectTest, MongoDBEngineTestBase):
    pass


class ResourceTest(base.ResourceTest, MongoDBEngineTestBase):
    pass


class ResourceTestPagination(base.ResourceTestPagination,
                             MongoDBEngineTestBase):
    pass


class MeterTest(base.MeterTest, MongoDBEngineTestBase):
    pass


class MeterTestPagination(base.MeterTestPagination, MongoDBEngineTestBase):
    pass


class RawSampleTest(base.RawSampleTest, MongoDBEngineTestBase):
    def test_clear_metering_data(self):
        # NOTE(sileht): ensure this tests is played for any version of mongo
        self.mox.StubOutWithMock(self.conn, "_is_natively_ttl_supported")
        self.conn._is_natively_ttl_supported().AndReturn(False)

        self.mox.ReplayAll()
        super(RawSampleTest, self).test_clear_metering_data()
        self.mox.UnsetStubs()
        self.mox.VerifyAll()

    def test_clear_metering_data_no_data_to_remove(self):
        # NOTE(sileht): ensure this tests is played for any version of mongo
        self.mox.StubOutWithMock(self.conn, "_is_natively_ttl_supported")
        self.conn._is_natively_ttl_supported().AndReturn(False)

        self.mox.ReplayAll()
        super(RawSampleTest, self).test_clear_metering_data_no_data_to_remove()
        self.mox.UnsetStubs()
        self.mox.VerifyAll()


class StatisticsTest(base.StatisticsTest, MongoDBEngineTestBase):
    pass


class AlarmTest(base.AlarmTest, MongoDBEngineTestBase):
    def prepare_old_matching_metadata_alarm(self):
        alarm = models.Alarm('old-alert',
                             'test.one', 'eq', 36, 'count',
                             'me', 'and-da-boys',
                             evaluation_periods=1,
                             period=60,
                             alarm_actions=['http://nowhere/alarms'],
                             matching_metadata={'key': 'value'})
        alarm.alarm_id = str(uuid.uuid1())
        data = alarm.as_dict()
        self.conn.db.alarm.update(
            {'alarm_id': alarm.alarm_id},
            {'$set': data},
            upsert=True)

    def test_alarm_get_old_matching_metadata_format(self):
        self.prepare_old_matching_metadata_alarm()
        old = list(self.conn.get_alarms(name='old-alert'))[0]
        self.assertEquals(old.matching_metadata, {'key': 'value'})


class CompatibilityTest(MongoDBEngineTestBase):

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
            return

        # Stubout with the old version DB schema, the one w/o 'counter_unit'
        self.stubs.Set(self.conn,
                       'record_metering_data',
                       old_record_metering_data)
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
                               }
        )
        self.counters.append(c)
        msg = rpc.meter_message_from_counter(
            c,
            secret='not-so-secret',
            source='test')
        self.conn.record_metering_data(self.conn, msg)

    def test_counter_unit(self):
        meters = list(self.conn.get_meters())
        self.assertEqual(len(meters), 1)


class AlarmTestPagination(base.AlarmTestPagination, MongoDBEngineTestBase):

    def test_alarm_get_marker(self):
        self.add_some_alarms()
        marker_pairs = {'name': 'red-alert'}
        ret = impl_mongodb.Connection._get_marker(self.conn.db.alarm,
                                                  marker_pairs=marker_pairs)
        self.assertEqual(ret['counter_name'], 'test.one')

    def test_alarm_get_marker_None(self):
        self.add_some_alarms()
        try:
            marker_pairs = {'name': 'user-id-foo'}
            ret = impl_mongodb.Connection._get_marker(self.conn.db.alarm,
                                                      marker_pairs)
            self.assertEqual(ret['counter_name'], 'counter_name-foo')
        except NoResultFound:
            self.assertTrue(True)

    def test_alarm_get_marker_multiple(self):
        self.add_some_alarms()
        try:
            marker_pairs = {'user_id': 'me'}
            ret = impl_mongodb.Connection._get_marker(self.conn.db.alarm,
                                                      marker_pairs)
            self.assertEqual(ret['counter_name'], 'counter-name-foo')
        except MultipleResultsFound:
            self.assertTrue(True)


class CounterDataTypeTest(base.CounterDataTypeTest, MongoDBEngineTestBase):
    pass
