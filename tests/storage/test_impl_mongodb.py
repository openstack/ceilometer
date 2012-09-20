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

  (dhellmann) These tests have some dependencies which cannot be
  installed in the CI environment right now.

  Ming is necessary to provide the Mongo-in-memory implementation for
  of MongoDB. The original source for Ming is at
  http://sourceforge.net/project/merciless but there does not seem to
  be a way to point to a "zipball" of the latest HEAD there, and we
  need features present only in that version. I forked the project to
  github to make it easier to install, and put the URL into the
  test-requires file. Then I ended up making some changes to it so it
  would be compatible with PyMongo's API.

    https://github.com/dreamhost/Ming/zipball/master#egg=Ming

  In order to run the tests that use map-reduce with MIM, some
  additional system-level packages are required::

    apt-get install nspr-config
    apt-get install libnspr4-dev
    apt-get install pkg-config
    pip install python-spidermonkey

  To run the tests *without* mim, set the environment variable
  CEILOMETER_TEST_LIVE=1 before running tox.

"""

import datetime
import logging
import os
import unittest

from ming import mim
import mox

from nose.plugins import skip

from ceilometer import counter
from ceilometer import meter
from ceilometer import storage
from ceilometer.storage import impl_mongodb


LOG = logging.getLogger(__name__)

FORCING_MONGO = bool(int(os.environ.get('CEILOMETER_TEST_LIVE', 0)))


class Connection(impl_mongodb.Connection):

    def _get_connection(self, conf):
        # Use a real MongoDB server if we can connect, but fall back
        # to a Mongo-in-memory connection if we cannot.
        if FORCING_MONGO:
            try:
                return super(Connection, self)._get_connection(conf)
            except:
                LOG.debug('Unable to connect to mongod')
                raise
        else:
            LOG.debug('Unable to connect to mongod, falling back to MIM')
            return mim.Connection()


class MongoDBEngineTestBase(unittest.TestCase):

    # Only instantiate the database config
    # and connection once, since spidermonkey
    # causes issues if we allocate too many
    # Runtime objects in the same process.
    # http://davisp.lighthouseapp.com/projects/26898/tickets/22
    conf = mox.Mox().CreateMockAnything()
    conf.database_connection = 'mongodb://localhost/testdb'
    conn = Connection(conf)

    def setUp(self):
        super(MongoDBEngineTestBase, self).setUp()

        self.conn.conn.drop_database('testdb')
        self.db = self.conn.conn['testdb']
        self.conn.db = self.db

        self.counter = counter.Counter(
            'test-1',
            'instance',
            'cumulative',
            1,
            'user-id',
            'project-id',
            'resource-id',
            timestamp=datetime.datetime(2012, 7, 2, 10, 40),
            duration=0,
            resource_metadata={'display_name': 'test-server',
                               'tag': 'self.counter',
                               }
            )
        self.msg = meter.meter_message_from_counter(self.counter)
        self.conn.record_metering_data(self.msg)

        self.counter2 = counter.Counter(
            'test-2',
            'instance',
            'cumulative',
            1,
            'user-id',
            'project-id',
            'resource-id-alternate',
            timestamp=datetime.datetime(2012, 7, 2, 10, 41),
            duration=0,
            resource_metadata={'display_name': 'test-server',
                               'tag': 'self.counter2',
                               }
            )
        self.msg2 = meter.meter_message_from_counter(self.counter2)
        self.conn.record_metering_data(self.msg2)

        self.counter3 = counter.Counter(
            'test-3',
            'instance',
            'cumulative',
            1,
            'user-id-alternate',
            'project-id',
            'resource-id-alternate',
            timestamp=datetime.datetime(2012, 7, 2, 10, 41),
            duration=0,
            resource_metadata={'display_name': 'test-server',
                               'tag': 'self.counter3',
                               }
            )
        self.msg3 = meter.meter_message_from_counter(self.counter3)
        self.conn.record_metering_data(self.msg3)

        for i in range(2, 4):
            c = counter.Counter(
                'test',
                'instance',
                'cumulative',
                1,
                'user-id-%s' % i,
                'project-id-%s' % i,
                'resource-id-%s' % i,
                timestamp=datetime.datetime(2012, 7, 2, 10, 40 + i),
                duration=0,
                resource_metadata={'display_name': 'test-server',
                                   'tag': 'counter-%s' % i,
                                   }
                )
            msg = meter.meter_message_from_counter(c)
            self.conn.record_metering_data(msg)


class UserTest(MongoDBEngineTestBase):

    def test_new_user(self):
        user = self.db.user.find_one({'_id': 'user-id'})
        assert user is not None

    def test_new_user_source(self):
        user = self.db.user.find_one({'_id': 'user-id'})
        assert 'source' in user
        assert user['source'] == ['test-1', 'test-2']

    def test_get_users(self):
        users = self.conn.get_users()
        assert set(users) == set(['user-id',
                                  'user-id-alternate',
                                  'user-id-2',
                                  'user-id-3',
                                  ])

    def test_get_users_by_source(self):
        users = list(self.conn.get_users(source='test-1'))
        assert len(users) == 1
        assert users == ['user-id']


class ProjectTest(MongoDBEngineTestBase):

    def test_new_project(self):
        project = self.db.project.find_one({'_id': 'project-id'})
        assert project is not None

    def test_new_project_source(self):
        project = self.db.project.find_one({'_id': 'project-id'})
        assert 'source' in project
        assert project['source'] == ['test-1', 'test-2', 'test-3']

    def test_get_projects(self):
        projects = self.conn.get_projects()
        expected = set(['project-id', 'project-id-2', 'project-id-3'])
        assert set(projects) == expected

    def test_get_projects_by_source(self):
        projects = self.conn.get_projects(source='test-1')
        expected = ['project-id']
        assert projects == expected


class ResourceTest(MongoDBEngineTestBase):

    def test_new_resource(self):
        resource = self.db.resource.find_one({'_id': 'resource-id'})
        assert resource is not None

    def test_new_resource_project(self):
        resource = self.db.resource.find_one({'_id': 'resource-id'})
        assert 'project_id' in resource
        assert resource['project_id'] == 'project-id'

    def test_new_resource_user(self):
        resource = self.db.resource.find_one({'_id': 'resource-id'})
        assert 'user_id' in resource
        assert resource['user_id'] == 'user-id'

    def test_new_resource_meter(self):
        resource = self.db.resource.find_one({'_id': 'resource-id'})
        assert 'meter' in resource
        assert resource['meter'] == [{'counter_name': 'instance',
                                      'counter_type': 'cumulative',
                                      }]

    def test_new_resource_metadata(self):
        resource = self.db.resource.find_one({'_id': 'resource-id'})
        assert 'metadata' in resource

    def test_get_resources(self):
        resources = list(self.conn.get_resources())
        assert len(resources) == 4
        for resource in resources:
            if resource['resource_id'] != 'resource-id':
                continue
            assert resource['resource_id'] == 'resource-id'
            assert resource['project_id'] == 'project-id'
            assert resource['user_id'] == 'user-id'
            assert 'metadata' in resource
            assert resource['meter'] == [{'counter_name': 'instance',
                                          'counter_type': 'cumulative',
                                          }]
            break
        else:
            assert False, 'Never found resource-id'

    def test_get_resources_start_timestamp(self):
        timestamp = datetime.datetime(2012, 7, 2, 10, 42)
        resources = list(self.conn.get_resources(start_timestamp=timestamp))
        resource_ids = [r['resource_id'] for r in resources]
        expected = set(['resource-id-2', 'resource-id-3'])
        assert set(resource_ids) == expected

    def test_get_resources_end_timestamp(self):
        timestamp = datetime.datetime(2012, 7, 2, 10, 42)
        resources = list(self.conn.get_resources(end_timestamp=timestamp))
        resource_ids = [r['resource_id'] for r in resources]
        expected = set(['resource-id', 'resource-id-alternate'])
        assert set(resource_ids) == expected

    def test_get_resources_both_timestamps(self):
        start_ts = datetime.datetime(2012, 7, 2, 10, 42)
        end_ts = datetime.datetime(2012, 7, 2, 10, 43)
        resources = list(self.conn.get_resources(start_timestamp=start_ts,
                                                 end_timestamp=end_ts)
                        )
        resource_ids = [r['resource_id'] for r in resources]
        expected = set(['resource-id-2'])
        assert set(resource_ids) == expected

    def test_get_resources_by_source(self):
        resources = list(self.conn.get_resources(source='test-1'))
        assert len(resources) == 1
        ids = set(r['resource_id'] for r in resources)
        assert ids == set(['resource-id'])

    def test_get_resources_by_user(self):
        resources = list(self.conn.get_resources(user='user-id'))
        num_resources = len(resources)
        assert num_resources == 1
        ids = set(r['resource_id'] for r in resources)
        assert ids == set(['resource-id'])

    def test_get_resources_by_project(self):
        resources = list(self.conn.get_resources(project='project-id'))
        assert len(resources) == 2
        ids = set(r['resource_id'] for r in resources)
        assert ids == set(['resource-id', 'resource-id-alternate'])


class MeterTest(MongoDBEngineTestBase):

    def test_new_meter(self):
        meter = self.db.meter.find_one()
        assert meter is not None

    def test_get_raw_events_by_user(self):
        f = storage.EventFilter(user='user-id')
        results = list(self.conn.get_raw_events(f))
        assert len(results) == 2
        for meter in results:
            assert meter in [self.msg, self.msg2]

    def test_get_raw_events_by_project(self):
        f = storage.EventFilter(project='project-id')
        results = list(self.conn.get_raw_events(f))
        assert results
        for meter in results:
            assert meter in [self.msg, self.msg2, self.msg3]

    def test_get_raw_events_by_resource(self):
        f = storage.EventFilter(user='user-id', resource='resource-id')
        results = list(self.conn.get_raw_events(f))
        assert results
        meter = results[0]
        assert meter is not None
        assert meter == self.msg

    def test_get_raw_events_by_start_time(self):
        f = storage.EventFilter(
            user='user-id',
            start=datetime.datetime(2012, 7, 2, 10, 41),
            )
        results = list(self.conn.get_raw_events(f))
        length = len(results)
        assert length == 1
        assert results[0]['timestamp'] == datetime.datetime(2012, 7, 2, 10, 41)

    def test_get_raw_events_by_end_time(self):
        f = storage.EventFilter(
            user='user-id',
            end=datetime.datetime(2012, 7, 2, 10, 41),
            )
        results = list(self.conn.get_raw_events(f))
        length = len(results)
        assert length == 1
        assert results[0]['timestamp'] == datetime.datetime(2012, 7, 2, 10, 40)

    def test_get_raw_events_by_both_times(self):
        f = storage.EventFilter(
            start=datetime.datetime(2012, 7, 2, 10, 42),
            end=datetime.datetime(2012, 7, 2, 10, 43),
            )
        results = list(self.conn.get_raw_events(f))
        length = len(results)
        assert length == 1
        assert results[0]['timestamp'] == datetime.datetime(2012, 7, 2, 10, 42)

    def test_get_raw_events_by_meter(self):
        f = storage.EventFilter(
            user='user-id',
            meter='no-such-meter',
            )
        results = list(self.conn.get_raw_events(f))
        assert not results

    def test_get_raw_events_by_meter2(self):
        f = storage.EventFilter(
            user='user-id',
            meter='instance',
            )
        results = list(self.conn.get_raw_events(f))
        assert results


class SumTest(MongoDBEngineTestBase):

    def setUp(self):
        super(SumTest, self).setUp()
        # NOTE(dhellmann): mim requires spidermonkey to implement the
        # map-reduce functions, so if we can't import it then just
        # skip these tests unless we aren't using mim.
        try:
            import spidermonkey
        except:
            if isinstance(self.conn.conn, mim.Connection):
                raise skip.SkipTest('requires spidermonkey')

    def test_by_user(self):
        f = storage.EventFilter(
            user='user-id',
            meter='instance',
            )
        results = list(self.conn.get_volume_sum(f))
        assert results
        counts = dict((r['resource_id'], r['value'])
                      for r in results)
        assert counts['resource-id'] == 1
        assert counts['resource-id-alternate'] == 1
        assert set(counts.keys()) == set(['resource-id',
                                          'resource-id-alternate'])

    def test_by_project(self):
        f = storage.EventFilter(
            project='project-id',
            meter='instance',
            )
        results = list(self.conn.get_volume_sum(f))
        assert results
        counts = dict((r['resource_id'], r['value'])
                      for r in results)
        assert counts['resource-id'] == 1
        assert counts['resource-id-alternate'] == 2
        assert set(counts.keys()) == set(['resource-id',
                                          'resource-id-alternate'])

    def test_one_resource(self):
        f = storage.EventFilter(
            user='user-id',
            meter='instance',
            resource='resource-id',
            )
        results = list(self.conn.get_volume_sum(f))
        assert results
        counts = dict((r['resource_id'], r['value'])
                      for r in results)
        assert counts['resource-id'] == 1
        assert set(counts.keys()) == set(['resource-id'])


class TestGetEventInterval(MongoDBEngineTestBase):

    def setUp(self):
        super(TestGetEventInterval, self).setUp()

        # NOTE(dhellmann): mim requires spidermonkey to implement the
        # map-reduce functions, so if we can't import it then just
        # skip these tests unless we aren't using mim.
        try:
            import spidermonkey
        except:
            if isinstance(self.conn.conn, mim.Connection):
                raise skip.SkipTest('requires spidermonkey')

        # Create events relative to the range and pretend
        # that the intervening events exist.

        self.start = datetime.datetime(2012, 8, 28, 0, 0)
        self.end = datetime.datetime(2012, 8, 29, 0, 0)

        self.early1 = self.start - datetime.timedelta(minutes=20)
        self.early2 = self.start - datetime.timedelta(minutes=10)

        self.middle1 = self.start + datetime.timedelta(minutes=10)
        self.middle2 = self.end - datetime.timedelta(minutes=10)

        self.late1 = self.end + datetime.timedelta(minutes=10)
        self.late2 = self.end + datetime.timedelta(minutes=20)

        self._filter = storage.EventFilter(
            resource='resource-id',
            meter='instance',
            start=self.start,
            end=self.end,
            )

    def _make_events(self, *timestamps):
        for t in timestamps:
            c = counter.Counter(
                'test',
                'instance',
                'cumulative',
                1,
                'user-id',
                'project-id',
                'resource-id',
                timestamp=t,
                duration=0,
                resource_metadata={'display_name': 'test-server',
                                   }
                )
            msg = meter.meter_message_from_counter(c)
            self.conn.record_metering_data(msg)

    def test_before_range(self):
        self._make_events(self.early1, self.early2)
        s, e = self.conn.get_event_interval(self._filter)
        assert s is None
        assert e is None

    def test_overlap_range_start(self):
        self._make_events(self.early1, self.start, self.middle1)
        s, e = self.conn.get_event_interval(self._filter)
        assert s == self.start
        assert e == self.middle1

    def test_within_range(self):
        self._make_events(self.middle1, self.middle2)
        s, e = self.conn.get_event_interval(self._filter)
        assert s == self.middle1
        assert e == self.middle2

    def test_within_range_zero_duration(self):
        self._make_events(self.middle1)
        s, e = self.conn.get_event_interval(self._filter)
        assert s == self.middle1
        assert e == self.middle1

    def test_within_range_zero_duration_two_events(self):
        self._make_events(self.middle1, self.middle1)
        s, e = self.conn.get_event_interval(self._filter)
        assert s == self.middle1
        assert e == self.middle1

    def test_overlap_range_end(self):
        self._make_events(self.middle2, self.end, self.late1)
        s, e = self.conn.get_event_interval(self._filter)
        assert s == self.middle2
        assert e == self.middle2

    def test_overlap_range_end_with_offset(self):
        self._make_events(self.middle2, self.end, self.late1)
        self._filter.end = self.late1
        s, e = self.conn.get_event_interval(self._filter)
        assert s == self.middle2
        assert e == self.end

    def test_after_range(self):
        self._make_events(self.late1, self.late2)
        s, e = self.conn.get_event_interval(self._filter)
        assert s is None
        assert e is None
