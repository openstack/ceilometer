# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Intel Corp.
#
# Author: Lianhao Lu <lianhao.lu@intel.com>
# Author: Shane Wang <shane.wang@intel.com>
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
""" Base classes for DB backend implemtation test
"""

import datetime

import testscenarios

from ceilometer.openstack.common.fixture import moxstubout
from ceilometer.openstack.common import timeutils
from ceilometer.publisher import rpc
from ceilometer import sample
from ceilometer import storage
from ceilometer.storage.base import Pagination
from ceilometer.storage import models
from ceilometer.tests import db as tests_db

load_tests = testscenarios.load_tests_apply_scenarios


class DBTestBase(tests_db.TestBase):
    def create_and_store_sample(self, timestamp=datetime.datetime.utcnow(),
                                metadata={
                                    'display_name': 'test-server',
                                    'tag': 'self.counter'
                                },
                                name='instance',
                                sample_type=sample.TYPE_CUMULATIVE, unit='',
                                volume=1, user_id='user-id',
                                project_id='project-id',
                                resource_id='resource-id', source=None):
        s = sample.Sample(
            name, sample_type, unit=unit, volume=volume, user_id=user_id,
            project_id=project_id, resource_id=resource_id,
            timestamp=timestamp,
            resource_metadata=metadata, source=source
        )
        msg = rpc.meter_message_from_counter(
            s, self.CONF.publisher_rpc.metering_secret
        )
        self.conn.record_metering_data(msg)
        return msg

    def setUp(self):
        super(DBTestBase, self).setUp()
        self.stubs = self.useFixture(moxstubout.MoxStubout()).stubs
        self.prepare_data()

    def tearDown(self):
        timeutils.utcnow.override_time = None
        super(DBTestBase, self).tearDown()

    def prepare_data(self):
        original_timestamps = [(2012, 7, 2, 10, 40), (2012, 7, 2, 10, 41),
                               (2012, 7, 2, 10, 41), (2012, 7, 2, 10, 42),
                               (2012, 7, 2, 10, 43)]

        timestamps_for_test_samples_default_order = [(2012, 7, 2, 10, 44),
                                                     (2011, 5, 30, 18, 3),
                                                     (2012, 12, 1, 1, 25),
                                                     (2012, 2, 29, 6, 59),
                                                     (2013, 5, 31, 23, 7)]
        timestamp_list = (original_timestamps +
                          timestamps_for_test_samples_default_order)

        self.msgs = []

        self.msgs.append(self.create_and_store_sample(
            timestamp=datetime.datetime(2012, 7, 2, 10, 39),
            source='test-1')
        )
        self.msgs.append(self.create_and_store_sample(
            timestamp=datetime.datetime(*timestamp_list[0]),
            source='test-1')
        )
        self.msgs.append(self.create_and_store_sample(
            timestamp=datetime.datetime(*timestamp_list[1]),
            resource_id='resource-id-alternate',
            metadata={'display_name': 'test-server', 'tag': 'self.counter2'},
            source='test-2')
        )
        self.msgs.append(self.create_and_store_sample(
            timestamp=datetime.datetime(*timestamp_list[2]),
            resource_id='resource-id-alternate',
            user_id='user-id-alternate',
            metadata={'display_name': 'test-server', 'tag': 'self.counter3'},
            source='test-3')
        )

        start_idx = 3
        end_idx = len(timestamp_list)

        for i, ts in zip(range(start_idx - 1, end_idx - 1),
                         timestamp_list[start_idx:end_idx]):
            self.msgs.append(
                self.create_and_store_sample(
                    timestamp=datetime.datetime(*ts),
                    user_id='user-id-%s' % i,
                    project_id='project-id-%s' % i,
                    resource_id='resource-id-%s' % i,
                    metadata={
                        'display_name': 'test-server',
                        'tag': 'counter-%s' % i
                    },
                    source='test')
            )


class UserTest(DBTestBase,
               tests_db.MixinTestsWithBackendScenarios):

    def test_get_users(self):
        users = self.conn.get_users()
        expected = set(['user-id', 'user-id-alternate', 'user-id-2',
                        'user-id-3', 'user-id-4', 'user-id-5', 'user-id-6',
                        'user-id-7', 'user-id-8'])
        self.assertEqual(set(users), expected)

    def test_get_users_by_source(self):
        users = self.conn.get_users(source='test-1')
        self.assertEqual(list(users), ['user-id'])


class ProjectTest(DBTestBase,
                  tests_db.MixinTestsWithBackendScenarios):

    def test_get_projects(self):
        projects = self.conn.get_projects()
        expected = set(['project-id', 'project-id-2', 'project-id-3',
                        'project-id-4', 'project-id-5', 'project-id-6',
                        'project-id-7', 'project-id-8'])
        self.assertEqual(set(projects), expected)

    def test_get_projects_by_source(self):
        projects = self.conn.get_projects(source='test-1')
        expected = ['project-id']
        self.assertEqual(list(projects), expected)


class ResourceTest(DBTestBase,
                   tests_db.MixinTestsWithBackendScenarios):

    def test_get_resources(self):
        expected_first_sample_timestamp = datetime.datetime(2012, 7, 2, 10, 39)
        expected_last_sample_timestamp = datetime.datetime(2012, 7, 2, 10, 40)
        msgs_sources = [msg['source'] for msg in self.msgs]
        resources = list(self.conn.get_resources())
        self.assertEqual(len(resources), 9)
        for resource in resources:
            if resource.resource_id != 'resource-id':
                continue
            self.assertEqual(resource.first_sample_timestamp,
                             expected_first_sample_timestamp)
            self.assertEqual(resource.last_sample_timestamp,
                             expected_last_sample_timestamp)
            self.assertEqual(resource.resource_id, 'resource-id')
            self.assertEqual(resource.project_id, 'project-id')
            self.assertIn(resource.source, msgs_sources)
            self.assertEqual(resource.user_id, 'user-id')
            self.assertEqual(resource.metadata['display_name'], 'test-server')
            self.assertIn(models.ResourceMeter('instance', 'cumulative', ''),
                          resource.meter)
            break
        else:
            assert False, 'Never found resource-id'

    def test_get_resources_start_timestamp(self):
        timestamp = datetime.datetime(2012, 7, 2, 10, 42)
        expected = set(['resource-id-2', 'resource-id-3', 'resource-id-4',
                        'resource-id-6', 'resource-id-8'])

        resources = list(self.conn.get_resources(start_timestamp=timestamp))
        resource_ids = [r.resource_id for r in resources]
        self.assertEqual(set(resource_ids), expected)

        resources = list(self.conn.get_resources(start_timestamp=timestamp,
                                                 start_timestamp_op='ge'))
        resource_ids = [r.resource_id for r in resources]
        self.assertEqual(set(resource_ids), expected)

        resources = list(self.conn.get_resources(start_timestamp=timestamp,
                                                 start_timestamp_op='gt'))
        resource_ids = [r.resource_id for r in resources]
        expected.remove('resource-id-2')
        self.assertEqual(set(resource_ids), expected)

    def test_get_resources_end_timestamp(self):
        timestamp = datetime.datetime(2012, 7, 2, 10, 42)
        expected = set(['resource-id', 'resource-id-alternate',
                        'resource-id-5', 'resource-id-7'])

        resources = list(self.conn.get_resources(end_timestamp=timestamp))
        resource_ids = [r.resource_id for r in resources]
        self.assertEqual(set(resource_ids), expected)

        resources = list(self.conn.get_resources(end_timestamp=timestamp,
                                                 end_timestamp_op='lt'))
        resource_ids = [r.resource_id for r in resources]
        self.assertEqual(set(resource_ids), expected)

        resources = list(self.conn.get_resources(end_timestamp=timestamp,
                                                 end_timestamp_op='le'))
        resource_ids = [r.resource_id for r in resources]
        expected.add('resource-id-2')
        self.assertEqual(set(resource_ids), expected)

    def test_get_resources_both_timestamps(self):
        start_ts = datetime.datetime(2012, 7, 2, 10, 42)
        end_ts = datetime.datetime(2012, 7, 2, 10, 43)

        resources = list(self.conn.get_resources(start_timestamp=start_ts,
                                                 end_timestamp=end_ts))
        resource_ids = [r.resource_id for r in resources]
        self.assertEqual(set(resource_ids), set(['resource-id-2']))

        resources = list(self.conn.get_resources(start_timestamp=start_ts,
                                                 end_timestamp=end_ts,
                                                 start_timestamp_op='ge',
                                                 end_timestamp_op='lt'))
        resource_ids = [r.resource_id for r in resources]
        self.assertEqual(set(resource_ids), set(['resource-id-2']))

        resources = list(self.conn.get_resources(start_timestamp=start_ts,
                                                 end_timestamp=end_ts,
                                                 start_timestamp_op='gt',
                                                 end_timestamp_op='lt'))
        resource_ids = [r.resource_id for r in resources]
        self.assertEqual(len(resource_ids), 0)

        resources = list(self.conn.get_resources(start_timestamp=start_ts,
                                                 end_timestamp=end_ts,
                                                 start_timestamp_op='gt',
                                                 end_timestamp_op='le'))
        resource_ids = [r.resource_id for r in resources]
        self.assertEqual(set(resource_ids), set(['resource-id-3']))

        resources = list(self.conn.get_resources(start_timestamp=start_ts,
                                                 end_timestamp=end_ts,
                                                 start_timestamp_op='ge',
                                                 end_timestamp_op='le'))
        resource_ids = [r.resource_id for r in resources]
        self.assertEqual(set(resource_ids),
                         set(['resource-id-2', 'resource-id-3']))

    def test_get_resources_by_source(self):
        resources = list(self.conn.get_resources(source='test-1'))
        self.assertEqual(len(resources), 1)
        ids = set(r.resource_id for r in resources)
        self.assertEqual(ids, set(['resource-id']))

    def test_get_resources_by_user(self):
        resources = list(self.conn.get_resources(user='user-id'))
        self.assertEqual(len(resources), 2)
        ids = set(r.resource_id for r in resources)
        self.assertEqual(ids, set(['resource-id', 'resource-id-alternate']))

    def test_get_resources_by_project(self):
        resources = list(self.conn.get_resources(project='project-id'))
        self.assertEqual(len(resources), 2)
        ids = set(r.resource_id for r in resources)
        self.assertEqual(ids, set(['resource-id', 'resource-id-alternate']))

    def test_get_resources_by_metaquery(self):
        q = {'metadata.display_name': 'test-server'}
        resources = list(self.conn.get_resources(metaquery=q))
        self.assertEqual(len(resources), 9)

    def test_get_resources_by_empty_metaquery(self):
        resources = list(self.conn.get_resources(metaquery={}))
        self.assertEqual(len(resources), 9)

    def test_get_resources_most_recent_metadata_all(self):
        resources = self.conn.get_resources()
        expected_tags = ['self.counter', 'self.counter3', 'counter-2',
                         'counter-3', 'counter-4', 'counter-5', 'counter-6',
                         'counter-7', 'counter-8']

        for resource in resources:
            self.assertIn(resource.metadata['tag'], expected_tags)

    def test_get_resources_most_recent_metadata_single(self):
        resource = list(
            self.conn.get_resources(resource='resource-id-alternate')
        )[0]
        expected_tag = 'self.counter3'
        self.assertEqual(resource.metadata['tag'], expected_tag)


class ResourceTestPagination(DBTestBase,
                             tests_db.MixinTestsWithBackendScenarios):

    def test_get_resource_all_limit(self):
        pagination = Pagination(limit=8)
        results = list(self.conn.get_resources(pagination=pagination))
        self.assertEqual(len(results), 8)

        pagination = Pagination(limit=5)
        results = list(self.conn.get_resources(pagination=pagination))
        self.assertEqual(len(results), 5)

    def test_get_resources_all_marker(self):
        pagination = Pagination(primary_sort_dir='asc', sort_keys=['user_id'],
                                sort_dirs=['asc'],
                                marker_value='resource-id-4')
        results = list(self.conn.get_resources(pagination=pagination))
        self.assertEqual(len(results), 5)

    def test_get_resources_paginate(self):
        pagination = Pagination(limit=3, primary_sort_dir='asc',
                                sort_keys=['user_id'], sort_dirs=['asc'],
                                marker_value='resource-id-4')
        results = self.conn.get_resources(pagination=pagination)
        self.assertEqual(['user-id-5', 'user-id-6', 'user-id-7'],
                         [i.user_id for i in results])

        pagination = Pagination(limit=2, primary_sort_dir='desc',
                                sort_keys=['user_id'], sort_dirs=['asc'],
                                marker_value='resource-id-4')
        results = list(self.conn.get_resources(pagination=pagination))
        self.assertEqual(['user-id-3', 'user-id-2'],
                         [i.user_id for i in results])

        pagination = Pagination(limit=3, primary_sort_dir='asc',
                                sort_keys=['user_id'], sort_dirs=['asc'],
                                marker_value='resource-id-5')
        results = list(self.conn.get_resources(pagination=pagination))
        self.assertEqual(['resource-id-6', 'resource-id-7', 'resource-id-8'],
                         [i.resource_id for i in results])


class ResourceTestOrdering(DBTestBase,
                           tests_db.MixinTestsWithBackendScenarios):
    def prepare_data(self):
        sample_timings = [('resource-id-1', [(2013, 8, 10, 10, 43),
                                             (2013, 8, 10, 10, 44),
                                             (2013, 8, 10, 10, 42),
                                             (2013, 8, 10, 10, 49),
                                             (2013, 8, 10, 10, 47)]),
                          ('resource-id-2', [(2013, 8, 10, 10, 43),
                                             (2013, 8, 10, 10, 48),
                                             (2013, 8, 10, 10, 42),
                                             (2013, 8, 10, 10, 48),
                                             (2013, 8, 10, 10, 47)]),
                          ('resource-id-3', [(2013, 8, 10, 10, 43),
                                             (2013, 8, 10, 10, 44),
                                             (2013, 8, 10, 10, 50),
                                             (2013, 8, 10, 10, 49),
                                             (2013, 8, 10, 10, 47)])]

        counter = 0
        for resource, timestamps in sample_timings:
            for timestamp in timestamps:
                self.create_and_store_sample(
                    timestamp=datetime.datetime(*timestamp),
                    resource_id=resource,
                    user_id=str(counter % 2),
                    project_id=str(counter % 3),
                    metadata={
                        'display_name': 'test-server',
                        'tag': 'sample-%s' % counter
                    },
                    source='test'
                )
                counter += 1

    def test_get_resources_ordering_all(self):
        resources = list(self.conn.get_resources())
        expected = set([
            ('resource-id-1', 'sample-3'),
            ('resource-id-2', 'sample-8'),
            ('resource-id-3', 'sample-12')
        ])
        received = set([(r.resource_id, r.metadata['tag']) for r in resources])
        self.assertEqual(received, expected)

    def test_get_resources_ordering_single(self):
        resource = list(self.conn.get_resources(resource='resource-id-2'))[0]
        self.assertEqual(resource.resource_id, 'resource-id-2')
        self.assertEqual(resource.metadata['tag'], 'sample-8')


class MeterTest(DBTestBase,
                tests_db.MixinTestsWithBackendScenarios):

    def test_get_meters(self):
        msgs_sources = [msg['source'] for msg in self.msgs]
        results = list(self.conn.get_meters())
        self.assertEqual(len(results), 9)
        for meter in results:
            self.assertIn(meter.source, msgs_sources)

    def test_get_meters_by_user(self):
        results = list(self.conn.get_meters(user='user-id'))
        self.assertEqual(len(results), 1)

    def test_get_meters_by_project(self):
        results = list(self.conn.get_meters(project='project-id'))
        self.assertEqual(len(results), 2)

    def test_get_meters_by_metaquery(self):
        q = {'metadata.display_name': 'test-server'}
        results = list(self.conn.get_meters(metaquery=q))
        assert results
        self.assertEqual(len(results), 9)

    def test_get_meters_by_empty_metaquery(self):
        results = list(self.conn.get_meters(metaquery={}))
        self.assertEqual(len(results), 9)


class MeterTestPagination(DBTestBase,
                          tests_db.MixinTestsWithBackendScenarios):

    def tet_get_meters_all_limit(self):
        pagination = Pagination(limit=8)
        results = list(self.conn.get_meters(pagination=pagination))
        self.assertEqual(len(results), 8)

        pagination = Pagination(limit=5)
        results = list(self.conn.get_meters(pagination=pagination))
        self.assertEqual(len(results), 5)

    def test_get_meters_all_marker(self):
        pagination = Pagination(limit=3, primary_sort_dir='desc',
                                sort_keys=['user_id'], sort_dirs=['desc'],
                                marker_value='resource-id-5')

        results = list(self.conn.get_meters(pagination=pagination))
        self.assertEqual(len(results), 8)

    def test_get_meters_paginate(self):
        pagination = Pagination(limit=3, primary_sort_dir='desc',
                                sort_keys=['user_id'], sort_dirs=['desc'],
                                marker_value='resource-id-5')
        results = self.conn.get_meters(pagination=pagination)
        self.assertEqual(['user-id-8', 'user-id-7', 'user-id-6'],
                         [i.user_id for i in results])

        pagination = Pagination(limit=3, primary_sort_dir='asc',
                                sort_keys=['user_id'], sort_dirs=['desc'],
                                marker_value='resource-id-5')
        results = self.conn.get_meters(pagination=pagination)
        self.assertEqual(['user-id-5', 'user-id-6', 'user-id-7'],
                         [i.user_id for i in results])

        pagination = Pagination(limit=2, primary_sort_dir='desc',
                                sort_keys=['user_id'], sort_dirs=['desc'],
                                marker_value='resource-id-5')
        results = list(self.conn.get_meters(pagination=pagination))
        self.assertEqual(['user-id-3', 'user-id-2'],
                         [i.user_id for i in results])

        pagination = Pagination(limit=3, primary_sort_dir='desc',
                                sort_keys=['user_id'], sort_dirs=['desc'],
                                marker_value='resource-id-5')
        results = self.conn.get_meters(pagination=pagination)
        self.assertEqual([], [i.user_id for i in results])


class RawSampleTest(DBTestBase,
                    tests_db.MixinTestsWithBackendScenarios):

    def test_get_samples_limit_zero(self):
        f = storage.SampleFilter()
        results = list(self.conn.get_samples(f, limit=0))
        self.assertEqual(len(results), 0)

    def test_get_samples_limit(self):
        f = storage.SampleFilter()
        results = list(self.conn.get_samples(f, limit=3))
        self.assertEqual(len(results), 3)

    def test_get_samples_in_default_order(self):
        f = storage.SampleFilter()
        prev_timestamp = None
        for sample in self.conn.get_samples(f):
            if prev_timestamp is not None:
                self.assertTrue(prev_timestamp >= sample.timestamp)
            prev_timestamp = sample.timestamp

    def test_get_samples_by_user(self):
        f = storage.SampleFilter(user='user-id')
        results = list(self.conn.get_samples(f))
        self.assertEqual(len(results), 3)
        for meter in results:
            self.assertIn(meter.as_dict(), self.msgs[:3])

    def test_get_samples_by_user_limit(self):
        f = storage.SampleFilter(user='user-id')
        results = list(self.conn.get_samples(f, limit=1))
        self.assertEqual(len(results), 1)

    def test_get_samples_by_user_limit_bigger(self):
        f = storage.SampleFilter(user='user-id')
        results = list(self.conn.get_samples(f, limit=42))
        self.assertEqual(len(results), 3)

    def test_get_samples_by_project(self):
        f = storage.SampleFilter(project='project-id')
        results = list(self.conn.get_samples(f))
        assert results
        for meter in results:
            self.assertIn(meter.as_dict(), self.msgs[:4])

    def test_get_samples_by_resource(self):
        f = storage.SampleFilter(user='user-id', resource='resource-id')
        results = list(self.conn.get_samples(f))
        assert results
        meter = results[1]
        assert meter is not None
        self.assertEqual(meter.as_dict(), self.msgs[0])

    def test_get_samples_by_metaquery(self):
        q = {'metadata.display_name': 'test-server'}
        f = storage.SampleFilter(metaquery=q)
        results = list(self.conn.get_samples(f))
        assert results
        for meter in results:
            self.assertIn(meter.as_dict(), self.msgs)

    def test_get_samples_by_start_time(self):
        timestamp = datetime.datetime(2012, 7, 2, 10, 41)
        f = storage.SampleFilter(
            user='user-id',
            start=timestamp,
        )

        results = list(self.conn.get_samples(f))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].timestamp, timestamp)

        f.start_timestamp_op = 'ge'
        results = list(self.conn.get_samples(f))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].timestamp, timestamp)

        f.start_timestamp_op = 'gt'
        results = list(self.conn.get_samples(f))
        self.assertEqual(len(results), 0)

    def test_get_samples_by_end_time(self):
        timestamp = datetime.datetime(2012, 7, 2, 10, 40)
        f = storage.SampleFilter(
            user='user-id',
            end=timestamp,
        )

        results = list(self.conn.get_samples(f))
        self.assertEqual(len(results), 1)

        f.end_timestamp_op = 'lt'
        results = list(self.conn.get_samples(f))
        self.assertEqual(len(results), 1)

        f.end_timestamp_op = 'le'
        results = list(self.conn.get_samples(f))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[1].timestamp,
                         datetime.datetime(2012, 7, 2, 10, 39))

    def test_get_samples_by_both_times(self):
        start_ts = datetime.datetime(2012, 7, 2, 10, 42)
        end_ts = datetime.datetime(2012, 7, 2, 10, 43)
        f = storage.SampleFilter(
            start=start_ts,
            end=end_ts,
        )

        results = list(self.conn.get_samples(f))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].timestamp, start_ts)

        f.start_timestamp_op = 'gt'
        f.end_timestamp_op = 'lt'
        results = list(self.conn.get_samples(f))
        self.assertEqual(len(results), 0)

        f.start_timestamp_op = 'ge'
        f.end_timestamp_op = 'lt'
        results = list(self.conn.get_samples(f))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].timestamp, start_ts)

        f.start_timestamp_op = 'gt'
        f.end_timestamp_op = 'le'
        results = list(self.conn.get_samples(f))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].timestamp, end_ts)

        f.start_timestamp_op = 'ge'
        f.end_timestamp_op = 'le'
        results = list(self.conn.get_samples(f))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].timestamp, end_ts)
        self.assertEqual(results[1].timestamp, start_ts)

    def test_get_samples_by_name(self):
        f = storage.SampleFilter(user='user-id', meter='no-such-meter')
        results = list(self.conn.get_samples(f))
        assert not results

    def test_get_samples_by_name2(self):
        f = storage.SampleFilter(user='user-id', meter='instance')
        results = list(self.conn.get_samples(f))
        assert results

    def test_get_samples_by_source(self):
        f = storage.SampleFilter(source='test-1')
        results = list(self.conn.get_samples(f))
        self.assertEqual(len(results), 2)

    def test_clear_metering_data(self):
        # NOTE(jd) Override this test in MongoDB because our code doesn't clear
        # the collections, this is handled by MongoDB TTL feature.
        if self.CONF.database.connection.startswith('mongodb://'):
            return

        timeutils.utcnow.override_time = datetime.datetime(2012, 7, 2, 10, 45)
        self.conn.clear_expired_metering_data(3 * 60)
        f = storage.SampleFilter(meter='instance')
        results = list(self.conn.get_samples(f))
        self.assertEqual(len(results), 5)
        results = list(self.conn.get_users())
        self.assertEqual(len(results), 5)
        results = list(self.conn.get_projects())
        self.assertEqual(len(results), 5)
        results = list(self.conn.get_resources())
        self.assertEqual(len(results), 5)

    def test_clear_metering_data_no_data_to_remove(self):
        # NOTE(jd) Override this test in MongoDB because our code doesn't clear
        # the collections, this is handled by MongoDB TTL feature.
        if self.CONF.database.connection.startswith('mongodb://'):
            return

        timeutils.utcnow.override_time = datetime.datetime(2010, 7, 2, 10, 45)
        self.conn.clear_expired_metering_data(3 * 60)
        f = storage.SampleFilter(meter='instance')
        results = list(self.conn.get_samples(f))
        self.assertEqual(len(results), 11)
        results = list(self.conn.get_users())
        self.assertEqual(len(results), 9)
        results = list(self.conn.get_projects())
        self.assertEqual(len(results), 8)
        results = list(self.conn.get_resources())
        self.assertEqual(len(results), 9)


class StatisticsTest(DBTestBase,
                     tests_db.MixinTestsWithBackendScenarios):

    def prepare_data(self):
        for i in range(3):
            c = sample.Sample(
                'volume.size',
                'gauge',
                'GiB',
                5 + i,
                'user-id',
                'project1',
                'resource-id',
                timestamp=datetime.datetime(2012, 9, 25, 10 + i, 30 + i),
                resource_metadata={'display_name': 'test-volume',
                                   'tag': 'self.counter',
                                   },
                source='test',
            )
            msg = rpc.meter_message_from_counter(
                c,
                secret='not-so-secret',
            )
            self.conn.record_metering_data(msg)
        for i in range(3):
            c = sample.Sample(
                'volume.size',
                'gauge',
                'GiB',
                8 + i,
                'user-5',
                'project2',
                'resource-6',
                timestamp=datetime.datetime(2012, 9, 25, 10 + i, 30 + i),
                resource_metadata={'display_name': 'test-volume',
                                   'tag': 'self.counter',
                                   },
                source='test',
            )
            msg = rpc.meter_message_from_counter(
                c,
                secret='not-so-secret',
            )
            self.conn.record_metering_data(msg)

    def test_by_user(self):
        f = storage.SampleFilter(
            user='user-5',
            meter='volume.size',
        )
        results = list(self.conn.get_meter_statistics(f))[0]
        self.assertEqual(results.duration,
                         (datetime.datetime(2012, 9, 25, 12, 32)
                          - datetime.datetime(2012, 9, 25, 10, 30)).seconds)
        self.assertEqual(results.count, 3)
        self.assertEqual(results.unit, 'GiB')
        self.assertEqual(results.min, 8)
        self.assertEqual(results.max, 10)
        self.assertEqual(results.sum, 27)
        self.assertEqual(results.avg, 9)

    def test_no_period_in_query(self):
        f = storage.SampleFilter(
            user='user-5',
            meter='volume.size',
        )
        results = list(self.conn.get_meter_statistics(f))[0]
        self.assertEqual(results.period, 0)

    def test_period_is_int(self):
        f = storage.SampleFilter(
            meter='volume.size',
        )
        results = list(self.conn.get_meter_statistics(f))[0]
        self.assertIs(type(results.period), int)
        self.assertEqual(results.count, 6)

    def test_by_user_period(self):
        f = storage.SampleFilter(
            user='user-5',
            meter='volume.size',
            start='2012-09-25T10:28:00',
        )
        results = list(self.conn.get_meter_statistics(f, period=7200))
        self.assertEqual(len(results), 2)
        self.assertEqual(set(r.period_start for r in results),
                         set([datetime.datetime(2012, 9, 25, 10, 28),
                              datetime.datetime(2012, 9, 25, 12, 28)]))
        self.assertEqual(set(r.period_end for r in results),
                         set([datetime.datetime(2012, 9, 25, 12, 28),
                              datetime.datetime(2012, 9, 25, 14, 28)]))
        r = results[0]
        self.assertEqual(r.period_start,
                         datetime.datetime(2012, 9, 25, 10, 28))
        self.assertEqual(r.count, 2)
        self.assertEqual(r.unit, 'GiB')
        self.assertEqual(r.avg, 8.5)
        self.assertEqual(r.min, 8)
        self.assertEqual(r.max, 9)
        self.assertEqual(r.sum, 17)
        self.assertEqual(r.period, 7200)
        self.assertIsInstance(r.period, int)
        expected_end = r.period_start + datetime.timedelta(seconds=7200)
        self.assertEqual(r.period_end, expected_end)
        self.assertEqual(r.duration, 3660)
        self.assertEqual(r.duration_start,
                         datetime.datetime(2012, 9, 25, 10, 30))
        self.assertEqual(r.duration_end,
                         datetime.datetime(2012, 9, 25, 11, 31))

    def test_by_user_period_with_timezone(self):
        dates = [
            '2012-09-25T00:28:00-10:00',
            '2012-09-25T01:28:00-09:00',
            '2012-09-25T02:28:00-08:00',
            '2012-09-25T03:28:00-07:00',
            '2012-09-25T04:28:00-06:00',
            '2012-09-25T05:28:00-05:00',
            '2012-09-25T06:28:00-04:00',
            '2012-09-25T07:28:00-03:00',
            '2012-09-25T08:28:00-02:00',
            '2012-09-25T09:28:00-01:00',
            '2012-09-25T10:28:00Z',
            '2012-09-25T11:28:00+01:00',
            '2012-09-25T12:28:00+02:00',
            '2012-09-25T13:28:00+03:00',
            '2012-09-25T14:28:00+04:00',
            '2012-09-25T15:28:00+05:00',
            '2012-09-25T16:28:00+06:00',
            '2012-09-25T17:28:00+07:00',
            '2012-09-25T18:28:00+08:00',
            '2012-09-25T19:28:00+09:00',
            '2012-09-25T20:28:00+10:00',
            '2012-09-25T21:28:00+11:00',
            '2012-09-25T22:28:00+12:00',
        ]
        for date in dates:
            f = storage.SampleFilter(
                user='user-5',
                meter='volume.size',
                start=date
            )
            results = list(self.conn.get_meter_statistics(f, period=7200))
            self.assertEqual(len(results), 2)
            self.assertEqual(set(r.period_start for r in results),
                             set([datetime.datetime(2012, 9, 25, 10, 28),
                                  datetime.datetime(2012, 9, 25, 12, 28)]))
            self.assertEqual(set(r.period_end for r in results),
                             set([datetime.datetime(2012, 9, 25, 12, 28),
                                  datetime.datetime(2012, 9, 25, 14, 28)]))

    def test_by_user_period_start_end(self):
        f = storage.SampleFilter(
            user='user-5',
            meter='volume.size',
            start='2012-09-25T10:28:00',
            end='2012-09-25T11:28:00',
        )
        results = list(self.conn.get_meter_statistics(f, period=1800))
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r.period_start,
                         datetime.datetime(2012, 9, 25, 10, 28))
        self.assertEqual(r.count, 1)
        self.assertEqual(r.unit, 'GiB')
        self.assertEqual(r.avg, 8)
        self.assertEqual(r.min, 8)
        self.assertEqual(r.max, 8)
        self.assertEqual(r.sum, 8)
        self.assertEqual(r.period, 1800)
        self.assertEqual(r.period_end,
                         r.period_start + datetime.timedelta(seconds=1800))
        self.assertEqual(r.duration, 0)
        self.assertEqual(r.duration_start,
                         datetime.datetime(2012, 9, 25, 10, 30))
        self.assertEqual(r.duration_end,
                         datetime.datetime(2012, 9, 25, 10, 30))

    def test_by_project(self):
        f = storage.SampleFilter(
            meter='volume.size',
            resource='resource-id',
            start='2012-09-25T11:30:00',
            end='2012-09-25T11:32:00',
        )
        results = list(self.conn.get_meter_statistics(f))[0]
        self.assertEqual(results.duration, 0)
        self.assertEqual(results.count, 1)
        self.assertEqual(results.unit, 'GiB')
        self.assertEqual(results.min, 6)
        self.assertEqual(results.max, 6)
        self.assertEqual(results.sum, 6)
        self.assertEqual(results.avg, 6)

    def test_one_resource(self):
        f = storage.SampleFilter(
            user='user-id',
            meter='volume.size',
        )
        results = list(self.conn.get_meter_statistics(f))[0]
        self.assertEqual(results.duration,
                         (datetime.datetime(2012, 9, 25, 12, 32)
                          - datetime.datetime(2012, 9, 25, 10, 30)).seconds)
        self.assertEqual(results.count, 3)
        self.assertEqual(results.unit, 'GiB')
        self.assertEqual(results.min, 5)
        self.assertEqual(results.max, 7)
        self.assertEqual(results.sum, 18)
        self.assertEqual(results.avg, 6)


class StatisticsGroupByTest(DBTestBase,
                            tests_db.MixinTestsWithBackendScenarios):

    def prepare_data(self):
        test_sample_data = (
            {'volume': 2, 'user': 'user-1', 'project': 'project-1',
             'resource': 'resource-1', 'timestamp': (2013, 8, 1, 16, 10),
             'metadata_flavor': 'm1.tiny', 'metadata_event': 'event-1',
             'source': 'source-2'},
            {'volume': 2, 'user': 'user-1', 'project': 'project-2',
             'resource': 'resource-1', 'timestamp': (2013, 8, 1, 15, 37),
             'metadata_flavor': 'm1.large', 'metadata_event': 'event-1',
             'source': 'source-2'},
            {'volume': 1, 'user': 'user-2', 'project': 'project-1',
             'resource': 'resource-2', 'timestamp': (2013, 8, 1, 10, 11),
             'metadata_flavor': 'm1.tiny', 'metadata_event': 'event-2',
             'source': 'source-1'},
            {'volume': 1, 'user': 'user-2', 'project': 'project-1',
             'resource': 'resource-2', 'timestamp': (2013, 8, 1, 10, 40),
             'metadata_flavor': 'm1.large', 'metadata_event': 'event-2',
             'source': 'source-1'},
            {'volume': 2, 'user': 'user-2', 'project': 'project-1',
             'resource': 'resource-1', 'timestamp': (2013, 8, 1, 14, 59),
             'metadata_flavor': 'm1.large', 'metadata_event': 'event-2',
             'source': 'source-1'},
            {'volume': 4, 'user': 'user-2', 'project': 'project-2',
             'resource': 'resource-2', 'timestamp': (2013, 8, 1, 17, 28),
             'metadata_flavor': 'm1.large', 'metadata_event': 'event-2',
             'source': 'source-1'},
            {'volume': 4, 'user': 'user-3', 'project': 'project-1',
             'resource': 'resource-3', 'timestamp': (2013, 8, 1, 11, 22),
             'metadata_flavor': 'm1.tiny', 'metadata_event': 'event-2',
             'source': 'source-3'},
        )

        for test_sample in test_sample_data:
            c = sample.Sample(
                'instance',
                sample.TYPE_CUMULATIVE,
                unit='s',
                volume=test_sample['volume'],
                user_id=test_sample['user'],
                project_id=test_sample['project'],
                resource_id=test_sample['resource'],
                timestamp=datetime.datetime(*test_sample['timestamp']),
                resource_metadata={'flavor': test_sample['metadata_flavor'],
                                   'event': test_sample['metadata_event'], },
                source=test_sample['source'],
            )
            msg = rpc.meter_message_from_counter(
                c,
                self.CONF.publisher_rpc.metering_secret,
            )
            self.conn.record_metering_data(msg)

    def test_group_by_user(self):
        f = storage.SampleFilter(
            meter='instance',
        )
        results = list(self.conn.get_meter_statistics(f, groupby=['user_id']))
        self.assertEqual(len(results), 3)
        groupby_list = [r.groupby for r in results]
        groupby_keys_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.keys())
        groupby_vals_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.values())
        self.assertEqual(groupby_keys_set, set(['user_id']))
        self.assertEqual(groupby_vals_set, set(['user-1', 'user-2', 'user-3']))

        for r in results:
            if r.groupby == {'user_id': 'user-1'}:
                self.assertEqual(r.count, 2)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 2)
                self.assertEqual(r.max, 2)
                self.assertEqual(r.sum, 4)
                self.assertEqual(r.avg, 2)
            elif r.groupby == {'user_id': 'user-2'}:
                self.assertEqual(r.count, 4)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 1)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 8)
                self.assertEqual(r.avg, 2)
            elif r.groupby == {'user_id': 'user-3'}:
                self.assertEqual(r.count, 1)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 4)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 4)
                self.assertEqual(r.avg, 4)

    def test_group_by_resource(self):
        f = storage.SampleFilter(
            meter='instance',
        )
        results = list(self.conn.get_meter_statistics(f,
                                                      groupby=['resource_id']))
        self.assertEqual(len(results), 3)
        groupby_list = [r.groupby for r in results]
        groupby_keys_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.keys())
        groupby_vals_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.values())
        self.assertEqual(groupby_keys_set, set(['resource_id']))
        self.assertEqual(groupby_vals_set, set(['resource-1',
                                                'resource-2',
                                                'resource-3']))
        for r in results:
            if r.groupby == {'resource_id': 'resource-1'}:
                self.assertEqual(r.count, 3)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 2)
                self.assertEqual(r.max, 2)
                self.assertEqual(r.sum, 6)
                self.assertEqual(r.avg, 2)
            elif r.groupby == {'resource_id': 'resource-2'}:
                self.assertEqual(r.count, 3)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 1)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 6)
                self.assertEqual(r.avg, 2)
            elif r.groupby == {'resource_id': 'resource-3'}:
                self.assertEqual(r.count, 1)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 4)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 4)
                self.assertEqual(r.avg, 4)

    def test_group_by_project(self):
        f = storage.SampleFilter(
            meter='instance',
        )
        results = list(self.conn.get_meter_statistics(f,
                                                      groupby=['project_id']))
        self.assertEqual(len(results), 2)
        groupby_list = [r.groupby for r in results]
        groupby_keys_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.keys())
        groupby_vals_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.values())
        self.assertEqual(groupby_keys_set, set(['project_id']))
        self.assertEqual(groupby_vals_set, set(['project-1', 'project-2']))

        for r in results:
            if r.groupby == {'project_id': 'project-1'}:
                self.assertEqual(r.count, 5)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 1)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 10)
                self.assertEqual(r.avg, 2)
            elif r.groupby == {'project_id': 'project-2'}:
                self.assertEqual(r.count, 2)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 2)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 6)
                self.assertEqual(r.avg, 3)

    def test_group_by_source(self):
        f = storage.SampleFilter(
            meter='instance',
        )
        results = list(self.conn.get_meter_statistics(f, groupby=['source']))
        self.assertEqual(len(results), 3)
        groupby_list = [r.groupby for r in results]
        groupby_keys_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.keys())
        groupby_vals_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.values())
        self.assertEqual(groupby_keys_set, set(['source']))
        self.assertEqual(groupby_vals_set, set(['source-1',
                                                'source-2',
                                                'source-3']))

        for r in results:
            if r.groupby == {'source': 'source-1'}:
                self.assertEqual(r.count, 4)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 1)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 8)
                self.assertEqual(r.avg, 2)
            elif r.groupby == {'source': 'source-2'}:
                self.assertEqual(r.count, 2)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 2)
                self.assertEqual(r.max, 2)
                self.assertEqual(r.sum, 4)
                self.assertEqual(r.avg, 2)
            elif r.groupby == {'source': 'source-3'}:
                self.assertEqual(r.count, 1)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 4)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 4)
                self.assertEqual(r.avg, 4)

    def test_group_by_unknown_field(self):
        f = storage.SampleFilter(
            meter='instance',
        )
        # NOTE(terriyu): The MongoDB get_meter_statistics() returns a list
        # whereas the SQLAlchemy get_meter_statistics() returns a generator.
        # You have to apply list() to the SQLAlchemy generator to get it to
        # throw an error. The MongoDB get_meter_statistics() will throw an
        # error before list() is called. By using lambda, we can cover both
        # MongoDB and SQLAlchemy in a single test.
        self.assertRaises(
            NotImplementedError,
            lambda: list(self.conn.get_meter_statistics(f, groupby=['wtf']))
        )

    def test_group_by_metadata(self):
        # TODO(terriyu): test_group_by_metadata needs to be implemented.
        # This test should check grouping by a single metadata field.
        pass

    def test_group_by_multiple_regular(self):
        f = storage.SampleFilter(
            meter='instance',
        )
        results = list(self.conn.get_meter_statistics(f,
                                                      groupby=['user_id',
                                                               'resource_id']))
        self.assertEqual(len(results), 4)
        groupby_list = [r.groupby for r in results]
        groupby_keys_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.keys())
        groupby_vals_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.values())
        self.assertEqual(groupby_keys_set, set(['user_id', 'resource_id']))
        self.assertEqual(groupby_vals_set, set(['user-1', 'user-2',
                                                'user-3', 'resource-1',
                                                'resource-2', 'resource-3']))

        for r in results:
            if r.groupby == {'user_id': 'user-1', 'resource_id': 'resource-1'}:
                self.assertEqual(r.count, 2)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 2)
                self.assertEqual(r.max, 2)
                self.assertEqual(r.sum, 4)
                self.assertEqual(r.avg, 2)
            elif r.groupby == {'user_id': 'user-2',
                               'resource_id': 'resource-1'}:
                self.assertEqual(r.count, 1)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 2)
                self.assertEqual(r.max, 2)
                self.assertEqual(r.sum, 2)
                self.assertEqual(r.avg, 2)
            elif r.groupby == {'user_id': 'user-2',
                               'resource_id': 'resource-2'}:
                self.assertEqual(r.count, 3)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 1)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 6)
                self.assertEqual(r.avg, 2)
            elif r.groupby == {'user_id': 'user-3',
                               'resource_id': 'resource-3'}:
                self.assertEqual(r.count, 1)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 4)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 4)
                self.assertEqual(r.avg, 4)
            else:
                self.assertNotEqual(r.groupby, {'user_id': 'user-1',
                                                'resource_id': 'resource-2'})
                self.assertNotEqual(r.groupby, {'user_id': 'user-1',
                                                'resource_id': 'resource-3'})
                self.assertNotEqual(r.groupby, {'user_id': 'user-2',
                                                'resource_id': 'resource-3'})
                self.assertNotEqual(r.groupby, {'user_id': 'user-3',
                                                'resource_id': 'resource-1'})
                self.assertNotEqual(r.groupby, {'user_id': 'user-3',
                                                'resource_id': 'resource-2'})

    def test_group_by_multiple_metadata(self):
        # TODO(terriyu): test_group_by_multiple_metadata needs to be
        # implemented.
        # This test should check grouping by multiple metadata fields.
        pass

    def test_group_by_multiple_regular_metadata(self):
        # TODO(terriyu): test_group_by_multiple_regular_metadata needs to be
        # implemented.
        # This test should check grouping by a combination of regular and
        # metadata fields.
        pass

    def test_group_by_with_query_filter(self):
        f = storage.SampleFilter(
            meter='instance',
            project='project-1',
        )
        results = list(self.conn.get_meter_statistics(
            f,
            groupby=['resource_id']))
        self.assertEqual(len(results), 3)
        groupby_list = [r.groupby for r in results]
        groupby_keys_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.keys())
        groupby_vals_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.values())
        self.assertEqual(groupby_keys_set, set(['resource_id']))
        self.assertEqual(groupby_vals_set, set(['resource-1',
                                                'resource-2',
                                                'resource-3']))

        for r in results:
            if r.groupby == {'resource_id': 'resource-1'}:
                self.assertEqual(r.count, 2)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 2)
                self.assertEqual(r.max, 2)
                self.assertEqual(r.sum, 4)
                self.assertEqual(r.avg, 2)
            elif r.groupby == {'resource_id': 'resource-2'}:
                self.assertEqual(r.count, 2)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 1)
                self.assertEqual(r.max, 1)
                self.assertEqual(r.sum, 2)
                self.assertEqual(r.avg, 1)
            elif r.groupby == {'resource_id': 'resource-3'}:
                self.assertEqual(r.count, 1)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 4)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 4)
                self.assertEqual(r.avg, 4)

    def test_group_by_metadata_with_query_filter(self):
        # TODO(terriyu): test_group_by_metadata_with_query_filter needs to be
        # implemented.
        # This test should check grouping by a metadata field in combination
        # with a query filter.
        pass

    def test_group_by_with_query_filter_multiple(self):
        f = storage.SampleFilter(
            meter='instance',
            user='user-2',
            source='source-1',
        )
        results = list(self.conn.get_meter_statistics(
            f,
            groupby=['project_id', 'resource_id']))
        self.assertEqual(len(results), 3)
        groupby_list = [r.groupby for r in results]
        groupby_keys_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.keys())
        groupby_vals_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.values())
        self.assertEqual(groupby_keys_set, set(['project_id', 'resource_id']))
        self.assertEqual(groupby_vals_set, set(['project-1', 'project-2',
                                                'resource-1', 'resource-2']))

        for r in results:
            if r.groupby == {'project_id': 'project-1',
                             'resource_id': 'resource-1'}:
                self.assertEqual(r.count, 1)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 2)
                self.assertEqual(r.max, 2)
                self.assertEqual(r.sum, 2)
                self.assertEqual(r.avg, 2)
            elif r.groupby == {'project_id': 'project-1',
                               'resource_id': 'resource-2'}:
                self.assertEqual(r.count, 2)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 1)
                self.assertEqual(r.max, 1)
                self.assertEqual(r.sum, 2)
                self.assertEqual(r.avg, 1)
            elif r.groupby == {'project_id': 'project-2',
                               'resource_id': 'resource-2'}:
                self.assertEqual(r.count, 1)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 4)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 4)
                self.assertEqual(r.avg, 4)
            else:
                self.assertNotEqual(r.groupby, {'project_id': 'project-2',
                                                'resource_id': 'resource-1'})

    def test_group_by_metadata_with_query_filter_multiple(self):
        # TODO(terriyu): test_group_by_metadata_with_query_filter_multiple
        # needs to be implemented.
        # This test should check grouping by multiple metadata fields in
        # combination with a query filter.
        pass

    def test_group_by_with_period(self):
        f = storage.SampleFilter(
            meter='instance',
        )
        results = list(self.conn.get_meter_statistics(f,
                                                      period=7200,
                                                      groupby=['project_id']))
        self.assertEqual(len(results), 4)
        groupby_list = [r.groupby for r in results]
        groupby_keys_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.keys())
        groupby_vals_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.values())
        self.assertEqual(groupby_keys_set, set(['project_id']))
        self.assertEqual(groupby_vals_set, set(['project-1', 'project-2']))
        period_start_set = set([r.period_start for r in results])
        period_start_valid = set([datetime.datetime(2013, 8, 1, 10, 11),
                                  datetime.datetime(2013, 8, 1, 14, 11),
                                  datetime.datetime(2013, 8, 1, 16, 11)])
        self.assertEqual(period_start_set, period_start_valid)

        for r in results:
            if (r.groupby == {'project_id': 'project-1'} and
                    r.period_start == datetime.datetime(2013, 8, 1, 10, 11)):
                self.assertEqual(r.count, 3)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 1)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 6)
                self.assertEqual(r.avg, 2)
                self.assertEqual(r.duration, 4260)
                self.assertEqual(r.duration_start,
                                 datetime.datetime(2013, 8, 1, 10, 11))
                self.assertEqual(r.duration_end,
                                 datetime.datetime(2013, 8, 1, 11, 22))
                self.assertEqual(r.period, 7200)
                self.assertEqual(r.period_end,
                                 datetime.datetime(2013, 8, 1, 12, 11))
            elif (r.groupby == {'project_id': 'project-1'} and
                    r.period_start == datetime.datetime(2013, 8, 1, 14, 11)):
                self.assertEqual(r.count, 2)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 2)
                self.assertEqual(r.max, 2)
                self.assertEqual(r.sum, 4)
                self.assertEqual(r.avg, 2)
                self.assertEqual(r.duration, 4260)
                self.assertEqual(r.duration_start,
                                 datetime.datetime(2013, 8, 1, 14, 59))
                self.assertEqual(r.duration_end,
                                 datetime.datetime(2013, 8, 1, 16, 10))
                self.assertEqual(r.period, 7200)
                self.assertEqual(r.period_end,
                                 datetime.datetime(2013, 8, 1, 16, 11))
            elif (r.groupby == {'project_id': 'project-2'} and
                    r.period_start == datetime.datetime(2013, 8, 1, 14, 11)):
                self.assertEqual(r.count, 1)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 2)
                self.assertEqual(r.max, 2)
                self.assertEqual(r.sum, 2)
                self.assertEqual(r.avg, 2)
                self.assertEqual(r.duration, 0)
                self.assertEqual(r.duration_start,
                                 datetime.datetime(2013, 8, 1, 15, 37))
                self.assertEqual(r.duration_end,
                                 datetime.datetime(2013, 8, 1, 15, 37))
                self.assertEqual(r.period, 7200)
                self.assertEqual(r.period_end,
                                 datetime.datetime(2013, 8, 1, 16, 11))
            elif (r.groupby == {'project_id': 'project-2'} and
                    r.period_start == datetime.datetime(2013, 8, 1, 16, 11)):
                self.assertEqual(r.count, 1)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 4)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 4)
                self.assertEqual(r.avg, 4)
                self.assertEqual(r.duration, 0)
                self.assertEqual(r.duration_start,
                                 datetime.datetime(2013, 8, 1, 17, 28))
                self.assertEqual(r.duration_end,
                                 datetime.datetime(2013, 8, 1, 17, 28))
                self.assertEqual(r.period, 7200)
                self.assertEqual(r.period_end,
                                 datetime.datetime(2013, 8, 1, 18, 11))
            else:
                self.assertNotEqual([r.groupby, r.period_start],
                                    [{'project_id': 'project-1'},
                                     datetime.datetime(2013, 8, 1, 16, 11)])
                self.assertNotEqual([r.groupby, r.period_start],
                                    [{'project_id': 'project-2'},
                                     datetime.datetime(2013, 8, 1, 10, 11)])

    def test_group_by_metadata_with_period(self):
        # TODO(terriyu): test_group_by_metadata_with_period needs to be
        # implemented.
        # This test should check grouping by metadata fields in combination
        # with period grouping.
        pass

    def test_group_by_with_query_filter_and_period(self):
        f = storage.SampleFilter(
            meter='instance',
            source='source-1',
        )
        results = list(self.conn.get_meter_statistics(f,
                                                      period=7200,
                                                      groupby=['project_id']))
        self.assertEqual(len(results), 3)
        groupby_list = [r.groupby for r in results]
        groupby_keys_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.keys())
        groupby_vals_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.values())
        self.assertEqual(groupby_keys_set, set(['project_id']))
        self.assertEqual(groupby_vals_set, set(['project-1', 'project-2']))
        period_start_set = set([r.period_start for r in results])
        period_start_valid = set([datetime.datetime(2013, 8, 1, 10, 11),
                                  datetime.datetime(2013, 8, 1, 14, 11),
                                  datetime.datetime(2013, 8, 1, 16, 11)])
        self.assertEqual(period_start_set, period_start_valid)

        for r in results:
            if (r.groupby == {'project_id': 'project-1'} and
                    r.period_start == datetime.datetime(2013, 8, 1, 10, 11)):
                self.assertEqual(r.count, 2)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 1)
                self.assertEqual(r.max, 1)
                self.assertEqual(r.sum, 2)
                self.assertEqual(r.avg, 1)
                self.assertEqual(r.duration, 1740)
                self.assertEqual(r.duration_start,
                                 datetime.datetime(2013, 8, 1, 10, 11))
                self.assertEqual(r.duration_end,
                                 datetime.datetime(2013, 8, 1, 10, 40))
                self.assertEqual(r.period, 7200)
                self.assertEqual(r.period_end,
                                 datetime.datetime(2013, 8, 1, 12, 11))
            elif (r.groupby == {'project_id': 'project-1'} and
                    r.period_start == datetime.datetime(2013, 8, 1, 14, 11)):
                self.assertEqual(r.count, 1)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 2)
                self.assertEqual(r.max, 2)
                self.assertEqual(r.sum, 2)
                self.assertEqual(r.avg, 2)
                self.assertEqual(r.duration, 0)
                self.assertEqual(r.duration_start,
                                 datetime.datetime(2013, 8, 1, 14, 59))
                self.assertEqual(r.duration_end,
                                 datetime.datetime(2013, 8, 1, 14, 59))
                self.assertEqual(r.period, 7200)
                self.assertEqual(r.period_end,
                                 datetime.datetime(2013, 8, 1, 16, 11))
            elif (r.groupby == {'project_id': 'project-2'} and
                    r.period_start == datetime.datetime(2013, 8, 1, 16, 11)):
                self.assertEqual(r.count, 1)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 4)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 4)
                self.assertEqual(r.avg, 4)
                self.assertEqual(r.duration, 0)
                self.assertEqual(r.duration_start,
                                 datetime.datetime(2013, 8, 1, 17, 28))
                self.assertEqual(r.duration_end,
                                 datetime.datetime(2013, 8, 1, 17, 28))
                self.assertEqual(r.period, 7200)
                self.assertEqual(r.period_end,
                                 datetime.datetime(2013, 8, 1, 18, 11))
            else:
                self.assertNotEqual([r.groupby, r.period_start],
                                    [{'project_id': 'project-1'},
                                     datetime.datetime(2013, 8, 1, 16, 11)])
                self.assertNotEqual([r.groupby, r.period_start],
                                    [{'project_id': 'project-2'},
                                     datetime.datetime(2013, 8, 1, 10, 11)])

    def test_group_by_metadata_with_query_filter_and_period(self):
        # TODO(terriyu): test_group_by_metadata_with_query_filter_and_period
        # needs to be implemented.
        # This test should check grouping with metadata fields in combination
        # with a query filter and period grouping.
        pass

    def test_group_by_start_timestamp_after(self):
        f = storage.SampleFilter(
            meter='instance',
            start=datetime.datetime(2013, 8, 1, 17, 28, 1),
        )
        results = list(self.conn.get_meter_statistics(f,
                                                      groupby=['project_id']))

        self.assertEqual(results, [])

    def test_group_by_end_timestamp_before(self):
        f = storage.SampleFilter(
            meter='instance',
            end=datetime.datetime(2013, 8, 1, 10, 10, 59),
        )
        results = list(self.conn.get_meter_statistics(f,
                                                      groupby=['project_id']))

        self.assertEqual(results, [])

    def test_group_by_start_timestamp(self):
        f = storage.SampleFilter(
            meter='instance',
            start=datetime.datetime(2013, 8, 1, 14, 58),
        )
        results = list(self.conn.get_meter_statistics(f,
                                                      groupby=['project_id']))
        self.assertEqual(len(results), 2)
        groupby_list = [r.groupby for r in results]
        groupby_keys_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.keys())
        groupby_vals_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.values())
        self.assertEqual(groupby_keys_set, set(['project_id']))
        self.assertEqual(groupby_vals_set, set(['project-1', 'project-2']))

        for r in results:
            if r.groupby == {'project_id': 'project-1'}:
                self.assertEqual(r.count, 2)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 2)
                self.assertEqual(r.max, 2)
                self.assertEqual(r.sum, 4)
                self.assertEqual(r.avg, 2)
            elif r.groupby == {'project_id': 'project-2'}:
                self.assertEqual(r.count, 2)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 2)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 6)
                self.assertEqual(r.avg, 3)

    def test_group_by_end_timestamp(self):
        f = storage.SampleFilter(
            meter='instance',
            end=datetime.datetime(2013, 8, 1, 11, 45),
        )
        results = list(self.conn.get_meter_statistics(f,
                                                      groupby=['project_id']))
        self.assertEqual(len(results), 1)
        groupby_list = [r.groupby for r in results]
        groupby_keys_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.keys())
        groupby_vals_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.values())
        self.assertEqual(groupby_keys_set, set(['project_id']))
        self.assertEqual(groupby_vals_set, set(['project-1']))

        for r in results:
            if r.groupby == {'project_id': 'project-1'}:
                self.assertEqual(r.count, 3)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 1)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 6)
                self.assertEqual(r.avg, 2)

    def test_group_by_start_end_timestamp(self):
        f = storage.SampleFilter(
            meter='instance',
            start=datetime.datetime(2013, 8, 1, 8, 17, 3),
            end=datetime.datetime(2013, 8, 1, 23, 59, 59),
        )
        results = list(self.conn.get_meter_statistics(f,
                                                      groupby=['project_id']))
        self.assertEqual(len(results), 2)
        groupby_list = [r.groupby for r in results]
        groupby_keys_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.keys())
        groupby_vals_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.values())
        self.assertEqual(groupby_keys_set, set(['project_id']))
        self.assertEqual(groupby_vals_set, set(['project-1', 'project-2']))

        for r in results:
            if r.groupby == {'project_id': 'project-1'}:
                self.assertEqual(r.count, 5)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 1)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 10)
                self.assertEqual(r.avg, 2)
            elif r.groupby == {'project_id': 'project-2'}:
                self.assertEqual(r.count, 2)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 2)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 6)
                self.assertEqual(r.avg, 3)

    def test_group_by_start_end_timestamp_with_query_filter(self):
        f = storage.SampleFilter(
            meter='instance',
            project='project-1',
            start=datetime.datetime(2013, 8, 1, 11, 1),
            end=datetime.datetime(2013, 8, 1, 20, 0),
        )
        results = list(self.conn.get_meter_statistics(f,
                                                      groupby=['resource_id']))
        groupby_list = [r.groupby for r in results]
        groupby_keys_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.keys())
        groupby_vals_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.values())
        self.assertEqual(groupby_keys_set, set(['resource_id']))
        self.assertEqual(groupby_vals_set, set(['resource-1', 'resource-3']))

        for r in results:
            if r.groupby == {'resource_id': 'resource-1'}:
                self.assertEqual(r.count, 2)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 2)
                self.assertEqual(r.max, 2)
                self.assertEqual(r.sum, 4)
                self.assertEqual(r.avg, 2)
            elif r.groupby == {'resource_id': 'resource-3'}:
                self.assertEqual(r.count, 1)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 4)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 4)
                self.assertEqual(r.avg, 4)

    def test_group_by_start_end_timestamp_with_period(self):
        f = storage.SampleFilter(
            meter='instance',
            start=datetime.datetime(2013, 8, 1, 14, 0),
            end=datetime.datetime(2013, 8, 1, 17, 0),
        )
        results = list(self.conn.get_meter_statistics(f,
                                                      period=3600,
                                                      groupby=['project_id']))
        self.assertEqual(len(results), 3)
        groupby_list = [r.groupby for r in results]
        groupby_keys_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.keys())
        groupby_vals_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.values())
        self.assertEqual(groupby_keys_set, set(['project_id']))
        self.assertEqual(groupby_vals_set, set(['project-1', 'project-2']))
        period_start_set = set([r.period_start for r in results])
        period_start_valid = set([datetime.datetime(2013, 8, 1, 14, 0),
                                  datetime.datetime(2013, 8, 1, 15, 0),
                                  datetime.datetime(2013, 8, 1, 16, 0)])
        self.assertEqual(period_start_set, period_start_valid)

        for r in results:
            if (r.groupby == {'project_id': 'project-1'} and
                    r.period_start == datetime.datetime(2013, 8, 1, 14, 0)):
                self.assertEqual(r.count, 1)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 2)
                self.assertEqual(r.max, 2)
                self.assertEqual(r.sum, 2)
                self.assertEqual(r.avg, 2)
                self.assertEqual(r.duration, 0)
                self.assertEqual(r.duration_start,
                                 datetime.datetime(2013, 8, 1, 14, 59))
                self.assertEqual(r.duration_end,
                                 datetime.datetime(2013, 8, 1, 14, 59))
                self.assertEqual(r.period, 3600)
                self.assertEqual(r.period_end,
                                 datetime.datetime(2013, 8, 1, 15, 0))
            elif (r.groupby == {'project_id': 'project-1'} and
                    r.period_start == datetime.datetime(2013, 8, 1, 16, 0)):
                self.assertEqual(r.count, 1)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 2)
                self.assertEqual(r.max, 2)
                self.assertEqual(r.sum, 2)
                self.assertEqual(r.avg, 2)
                self.assertEqual(r.duration, 0)
                self.assertEqual(r.duration_start,
                                 datetime.datetime(2013, 8, 1, 16, 10))
                self.assertEqual(r.duration_end,
                                 datetime.datetime(2013, 8, 1, 16, 10))
                self.assertEqual(r.period, 3600)
                self.assertEqual(r.period_end,
                                 datetime.datetime(2013, 8, 1, 17, 0))
            elif (r.groupby == {'project_id': 'project-2'} and
                    r.period_start == datetime.datetime(2013, 8, 1, 15, 0)):
                self.assertEqual(r.count, 1)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 2)
                self.assertEqual(r.max, 2)
                self.assertEqual(r.sum, 2)
                self.assertEqual(r.avg, 2)
                self.assertEqual(r.duration, 0)
                self.assertEqual(r.duration_start,
                                 datetime.datetime(2013, 8, 1, 15, 37))
                self.assertEqual(r.duration_end,
                                 datetime.datetime(2013, 8, 1, 15, 37))
                self.assertEqual(r.period, 3600)
                self.assertEqual(r.period_end,
                                 datetime.datetime(2013, 8, 1, 16, 0))
            else:
                self.assertNotEqual([r.groupby, r.period_start],
                                    [{'project_id': 'project-1'},
                                     datetime.datetime(2013, 8, 1, 15, 0)])
                self.assertNotEqual([r.groupby, r.period_start],
                                    [{'project_id': 'project-2'},
                                     datetime.datetime(2013, 8, 1, 14, 0)])
                self.assertNotEqual([r.groupby, r.period_start],
                                    [{'project_id': 'project-2'},
                                     datetime.datetime(2013, 8, 1, 16, 0)])

    def test_group_by_start_end_timestamp_with_query_filter_and_period(self):
        f = storage.SampleFilter(
            meter='instance',
            source='source-1',
            start=datetime.datetime(2013, 8, 1, 10, 0),
            end=datetime.datetime(2013, 8, 1, 18, 0),
        )
        results = list(self.conn.get_meter_statistics(f,
                                                      period=7200,
                                                      groupby=['project_id']))
        self.assertEqual(len(results), 3)
        groupby_list = [r.groupby for r in results]
        groupby_keys_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.keys())
        groupby_vals_set = set(x for sub_dict in groupby_list
                               for x in sub_dict.values())
        self.assertEqual(groupby_keys_set, set(['project_id']))
        self.assertEqual(groupby_vals_set, set(['project-1', 'project-2']))
        period_start_set = set([r.period_start for r in results])
        period_start_valid = set([datetime.datetime(2013, 8, 1, 10, 0),
                                  datetime.datetime(2013, 8, 1, 14, 0),
                                  datetime.datetime(2013, 8, 1, 16, 0)])
        self.assertEqual(period_start_set, period_start_valid)

        for r in results:
            if (r.groupby == {'project_id': 'project-1'} and
                    r.period_start == datetime.datetime(2013, 8, 1, 10, 0)):
                self.assertEqual(r.count, 2)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 1)
                self.assertEqual(r.max, 1)
                self.assertEqual(r.sum, 2)
                self.assertEqual(r.avg, 1)
                self.assertEqual(r.duration, 1740)
                self.assertEqual(r.duration_start,
                                 datetime.datetime(2013, 8, 1, 10, 11))
                self.assertEqual(r.duration_end,
                                 datetime.datetime(2013, 8, 1, 10, 40))
                self.assertEqual(r.period, 7200)
                self.assertEqual(r.period_end,
                                 datetime.datetime(2013, 8, 1, 12, 0))
            elif (r.groupby == {'project_id': 'project-1'} and
                    r.period_start == datetime.datetime(2013, 8, 1, 14, 0)):
                self.assertEqual(r.count, 1)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 2)
                self.assertEqual(r.max, 2)
                self.assertEqual(r.sum, 2)
                self.assertEqual(r.avg, 2)
                self.assertEqual(r.duration, 0)
                self.assertEqual(r.duration_start,
                                 datetime.datetime(2013, 8, 1, 14, 59))
                self.assertEqual(r.duration_end,
                                 datetime.datetime(2013, 8, 1, 14, 59))
                self.assertEqual(r.period, 7200)
                self.assertEqual(r.period_end,
                                 datetime.datetime(2013, 8, 1, 16, 0))
            elif (r.groupby == {'project_id': 'project-2'} and
                    r.period_start == datetime.datetime(2013, 8, 1, 16, 0)):
                self.assertEqual(r.count, 1)
                self.assertEqual(r.unit, 's')
                self.assertEqual(r.min, 4)
                self.assertEqual(r.max, 4)
                self.assertEqual(r.sum, 4)
                self.assertEqual(r.avg, 4)
                self.assertEqual(r.duration, 0)
                self.assertEqual(r.duration_start,
                                 datetime.datetime(2013, 8, 1, 17, 28))
                self.assertEqual(r.duration_end,
                                 datetime.datetime(2013, 8, 1, 17, 28))
                self.assertEqual(r.period, 7200)
                self.assertEqual(r.period_end,
                                 datetime.datetime(2013, 8, 1, 18, 0))
            else:
                self.assertNotEqual([r.groupby, r.period_start],
                                    [{'project_id': 'project-1'},
                                     datetime.datetime(2013, 8, 1, 16, 0)])
                self.assertNotEqual([r.groupby, r.period_start],
                                    [{'project_id': 'project-2'},
                                     datetime.datetime(2013, 8, 1, 10, 0)])
                self.assertNotEqual([r.groupby, r.period_start],
                                    [{'project_id': 'project-2'},
                                     datetime.datetime(2013, 8, 1, 14, 0)])


class CounterDataTypeTest(DBTestBase,
                          tests_db.MixinTestsWithBackendScenarios):
    def prepare_data(self):
        c = sample.Sample(
            'dummyBigCounter',
            sample.TYPE_CUMULATIVE,
            unit='',
            volume=3372036854775807,
            user_id='user-id',
            project_id='project-id',
            resource_id='resource-id',
            timestamp=datetime.datetime(2012, 7, 2, 10, 40),
            resource_metadata={},
            source='test-1',
        )
        msg = rpc.meter_message_from_counter(
            c,
            self.CONF.publisher_rpc.metering_secret,
        )

        self.conn.record_metering_data(msg)

        c = sample.Sample(
            'dummySmallCounter',
            sample.TYPE_CUMULATIVE,
            unit='',
            volume=-3372036854775807,
            user_id='user-id',
            project_id='project-id',
            resource_id='resource-id',
            timestamp=datetime.datetime(2012, 7, 2, 10, 40),
            resource_metadata={},
            source='test-1',
        )
        msg = rpc.meter_message_from_counter(
            c,
            self.CONF.publisher_rpc.metering_secret,
        )
        self.conn.record_metering_data(msg)

        c = sample.Sample(
            'floatCounter',
            sample.TYPE_CUMULATIVE,
            unit='',
            volume=1938495037.53697,
            user_id='user-id',
            project_id='project-id',
            resource_id='resource-id',
            timestamp=datetime.datetime(2012, 7, 2, 10, 40),
            resource_metadata={},
            source='test-1',
        )
        msg = rpc.meter_message_from_counter(
            c,
            self.CONF.publisher_rpc.metering_secret,
        )
        self.conn.record_metering_data(msg)

    def test_storage_can_handle_large_values(self):
        f = storage.SampleFilter(
            meter='dummyBigCounter',
        )
        results = list(self.conn.get_samples(f))
        self.assertEqual(results[0].counter_volume, 3372036854775807)

        f = storage.SampleFilter(
            meter='dummySmallCounter',
        )
        results = list(self.conn.get_samples(f))
        self.assertEqual(results[0].counter_volume, -3372036854775807)

    def test_storage_can_handle_float_values(self):
        f = storage.SampleFilter(
            meter='floatCounter',
        )
        results = list(self.conn.get_samples(f))
        self.assertEqual(results[0].counter_volume, 1938495037.53697)


class AlarmTestBase(DBTestBase):
    def add_some_alarms(self):
        alarms = [models.Alarm(alarm_id='r3d',
                               enabled=True,
                               type='threshold',
                               name='red-alert',
                               description='my red-alert',
                               timestamp=None,
                               user_id='me',
                               project_id='and-da-boys',
                               state="insufficient data",
                               state_timestamp=None,
                               ok_actions=[],
                               alarm_actions=['http://nowhere/alarms'],
                               insufficient_data_actions=[],
                               repeat_actions=False,
                               rule=dict(comparison_operator='eq',
                                         threshold=36,
                                         statistic='count',
                                         evaluation_periods=1,
                                         period=60,
                                         meter_name='test.one',
                                         query=[{'field': 'key',
                                                 'op': 'eq',
                                                 'value': 'value',
                                                 'type': 'string'}]),
                               ),
                  models.Alarm(alarm_id='0r4ng3',
                               enabled=True,
                               type='threshold',
                               name='orange-alert',
                               description='a orange',
                               timestamp=None,
                               user_id='me',
                               project_id='and-da-boys',
                               state="insufficient data",
                               state_timestamp=None,
                               ok_actions=[],
                               alarm_actions=['http://nowhere/alarms'],
                               insufficient_data_actions=[],
                               repeat_actions=False,
                               rule=dict(comparison_operator='gt',
                                         threshold=75,
                                         statistic='avg',
                                         evaluation_periods=1,
                                         period=60,
                                         meter_name='test.fourty',
                                         query=[{'field': 'key2',
                                                 'op': 'eq',
                                                 'value': 'value2',
                                                 'type': 'string'}]),
                               ),
                  models.Alarm(alarm_id='y3ll0w',
                               enabled=False,
                               type='threshold',
                               name='yellow-alert',
                               description='yellow',
                               timestamp=None,
                               user_id='me',
                               project_id='and-da-boys',
                               state="insufficient data",
                               state_timestamp=None,
                               ok_actions=[],
                               alarm_actions=['http://nowhere/alarms'],
                               insufficient_data_actions=[],
                               repeat_actions=False,
                               rule=dict(comparison_operator='lt',
                                         threshold=10,
                                         statistic='min',
                                         evaluation_periods=1,
                                         period=60,
                                         meter_name='test.five',
                                         query=[{'field': 'key2',
                                                 'op': 'eq',
                                                 'value': 'value2',
                                                 'type': 'string'},
                                                {'field':
                                                 'user_metadata.key3',
                                                 'op': 'eq',
                                                 'value': 'value3',
                                                 'type': 'string'}]),
                               )]

        for a in alarms:
            self.conn.create_alarm(a)


class AlarmTest(AlarmTestBase,
                tests_db.MixinTestsWithBackendScenarios):

    def test_empty(self):
        alarms = list(self.conn.get_alarms())
        self.assertEqual([], alarms)

    def test_list(self):
        self.add_some_alarms()
        alarms = list(self.conn.get_alarms())
        self.assertEqual(len(alarms), 3)

    def test_list_enabled(self):
        self.add_some_alarms()
        alarms = list(self.conn.get_alarms(enabled=True))
        self.assertEqual(len(alarms), 2)

    def test_list_disabled(self):
        self.add_some_alarms()
        alarms = list(self.conn.get_alarms(enabled=False))
        self.assertEqual(len(alarms), 1)

    def test_add(self):
        self.add_some_alarms()
        alarms = list(self.conn.get_alarms())
        self.assertEqual(len(alarms), 3)
        self.assertEqual(alarms[0].rule['meter_name'], 'test.one')
        self.assertEqual(alarms[1].rule['meter_name'], 'test.fourty')
        self.assertEqual(alarms[2].rule['meter_name'], 'test.five')

    def test_update(self):
        self.add_some_alarms()
        orange = list(self.conn.get_alarms(name='orange-alert'))[0]
        orange.enabled = False
        orange.state = models.Alarm.ALARM_INSUFFICIENT_DATA
        query = [{'field': 'metadata.group',
                  'op': 'eq',
                  'value': 'test.updated',
                  'type': 'string'}]
        orange.rule['query'] = query
        orange.rule['meter_name'] = 'new_meter_name'
        updated = self.conn.update_alarm(orange)
        self.assertEqual(updated.enabled, False)
        self.assertEqual(updated.state, models.Alarm.ALARM_INSUFFICIENT_DATA)
        self.assertEqual(updated.rule['query'], query)
        self.assertEqual(updated.rule['meter_name'], 'new_meter_name')

    def test_update_llu(self):
        llu = models.Alarm(alarm_id='llu',
                           enabled=True,
                           type='threshold',
                           name='llu',
                           description='llu',
                           timestamp=None,
                           user_id='bla',
                           project_id='ffo',
                           state="insufficient data",
                           state_timestamp=None,
                           ok_actions=[],
                           alarm_actions=[],
                           insufficient_data_actions=[],
                           repeat_actions=False,
                           rule=dict(comparison_operator='lt',
                                     threshold=34,
                                     statistic='max',
                                     evaluation_periods=1,
                                     period=60,
                                     meter_name='llt',
                                     query=[])
                           )
        updated = self.conn.update_alarm(llu)
        updated.state = models.Alarm.ALARM_OK
        updated.description = ':)'
        self.conn.update_alarm(updated)

        all = list(self.conn.get_alarms())
        self.assertEqual(len(all), 1)

    def test_delete(self):
        self.add_some_alarms()
        victim = list(self.conn.get_alarms(name='orange-alert'))[0]
        self.conn.delete_alarm(victim.alarm_id)
        survivors = list(self.conn.get_alarms())
        self.assertEqual(len(survivors), 2)
        for s in survivors:
            self.assertNotEquals(victim.name, s.name)


class AlarmTestPagination(AlarmTestBase,
                          tests_db.MixinTestsWithBackendScenarios):

    def test_get_alarm_all_limit(self):
        self.add_some_alarms()
        pagination = Pagination(limit=2)
        alarms = list(self.conn.get_alarms(pagination=pagination))
        self.assertEqual(len(alarms), 2)

        pagination = Pagination(limit=1)
        alarms = list(self.conn.get_alarms(pagination=pagination))
        self.assertEqual(len(alarms), 1)

    def test_get_alarm_all_marker(self):
        self.add_some_alarms()

        pagination = Pagination(marker_value='orange-alert')
        alarms = list(self.conn.get_alarms(pagination=pagination))
        self.assertEqual(len(alarms), 0)

        pagination = Pagination(marker_value='red-alert')
        alarms = list(self.conn.get_alarms(pagination=pagination))
        self.assertEqual(len(alarms), 1)

        pagination = Pagination(marker_value='yellow-alert')
        alarms = list(self.conn.get_alarms(pagination=pagination))
        self.assertEqual(len(alarms), 2)

    def test_get_alarm_paginate(self):

        self.add_some_alarms()

        pagination = Pagination(limit=4, marker_value='yellow-alert')
        page = list(self.conn.get_alarms(pagination=pagination))
        self.assertEqual(['red-alert', 'orange-alert'], [i.name for i in page])

        pagination = Pagination(limit=2, marker_value='orange-alert',
                                primary_sort_dir='asc')
        page1 = list(self.conn.get_alarms(pagination=pagination))
        self.assertEqual(['red-alert', 'yellow-alert'],
                         [i.name for i in page1])


class EventTestBase(tests_db.TestBase,
                    tests_db.MixinTestsWithBackendScenarios):
    """Separate test base class because we don't want to
    inherit all the Meter stuff.
    """

    def setUp(self):
        super(EventTestBase, self).setUp()
        self.prepare_data()

    def prepare_data(self):
        # Add some data ...
        pass


class EventTest(EventTestBase):
    def test_duplicate_message_id(self):
        now = datetime.datetime.utcnow()
        m = [models.Event("1", "Foo", now, None),
             models.Event("1", "Zoo", now, [])]
        problem_events = self.conn.record_events(m)
        self.assertEqual(1, len(problem_events))
        bad = problem_events[0]
        self.assertEqual(models.Event.DUPLICATE, bad[0])


class GetEventTest(EventTestBase):
    def prepare_data(self):
        event_models = []
        base = 0
        self.start = datetime.datetime(2013, 12, 31, 5, 0)
        now = self.start
        for event_name in ['Foo', 'Bar', 'Zoo']:
            trait_models = \
                [models.Trait(name, dtype, value)
                    for name, dtype, value in [
                        ('trait_A', models.Trait.TEXT_TYPE,
                            "my_%s_text" % event_name),
                        ('trait_B', models.Trait.INT_TYPE,
                            base + 1),
                        ('trait_C', models.Trait.FLOAT_TYPE,
                            float(base) + 0.123456),
                        ('trait_D', models.Trait.DATETIME_TYPE, now)]]
            event_models.append(
                models.Event("id_%s" % event_name,
                             event_name, now, trait_models))
            base += 100
            now = now + datetime.timedelta(hours=1)
        self.end = now

        prob = self.conn.record_events(event_models)
        self.assertEqual(0, len(prob), prob)

    def test_simple_get(self):
        event_filter = storage.EventFilter(self.start, self.end)
        events = self.conn.get_events(event_filter)
        #self.fail(self.conn.get_traits())
        self.assertEqual(3, len(events))
        start_time = None
        for i, name in enumerate(["Foo", "Bar", "Zoo"]):
            self.assertEqual(events[i].event_name, name)
            self.assertEqual(4, len(events[i].traits))
            # Ensure sorted results ...
            if start_time is not None:
                # Python 2.6 has no assertLess :(
                self.assertTrue(start_time < events[i].generated)
            start_time = events[i].generated

    def test_simple_get_event_name(self):
        event_filter = storage.EventFilter(self.start, self.end, "Bar")
        events = self.conn.get_events(event_filter)
        self.assertEqual(1, len(events))
        self.assertEqual(events[0].event_name, "Bar")
        self.assertEqual(4, len(events[0].traits))

    def test_get_event_trait_filter(self):
        trait_filters = {'key': 'trait_B', 't_int': 101}
        event_filter = storage.EventFilter(self.start, self.end,
                                           traits=trait_filters)
        events = self.conn.get_events(event_filter)
        self.assertEqual(1, len(events))
        self.assertEqual(events[0].event_name, "Bar")
        self.assertEqual(4, len(events[0].traits))

    def test_simple_get_no_traits(self):
        new_events = [models.Event("id_notraits", "NoTraits", self.start, [])]
        bad_events = self.conn.record_events(new_events)
        event_filter = storage.EventFilter(self.start, self.end, "NoTraits")
        events = self.conn.get_events(event_filter)
        self.assertEquals(0, len(bad_events))
        self.assertEqual(1, len(events))
        self.assertEqual(events[0].message_id, "id_notraits")
        self.assertEqual(events[0].event_name, "NoTraits")
        self.assertEqual(0, len(events[0].traits))
