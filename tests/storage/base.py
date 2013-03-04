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

import abc
import datetime

from oslo.config import cfg

from ceilometer.collector import meter
from ceilometer import counter
from ceilometer import storage
from ceilometer.tests import base as test_base


class DBEngineBase(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def get_connection(self):
        """Return an open connection to the DB
        """

    @abc.abstractmethod
    def clean_up(self):
        """Clean up all resources allocated in get_connection()
        """

    @abc.abstractmethod
    def get_sources_by_project_id(self, id):
        """Return a list of source strings of the matching project.

        :param id: id string value of the matching project.
        """

    @abc.abstractmethod
    def get_sources_by_user_id(self, id):
        """Return a list of source strings of the matching user.

        :param id: id string value of the matching user.
        """


class DBTestBase(test_base.TestCase):
    __metaclass__ = abc.ABCMeta

    @classmethod
    @abc.abstractmethod
    def get_engine(cls):
        '''Return an instance of the class which implements
           the DBEngineTestBase abstract class
        '''

    def tearDown(self):
        self.engine.clean_up()
        self.conn = None
        self.engine = None
        super(DBTestBase, self).tearDown()

    def setUp(self):
        super(DBTestBase, self).setUp()
        # TODO(jd) remove, use test_base.TestCase setUp to do that
        self.engine = self.get_engine()
        self.conn = self.engine.get_connection()
        self.prepare_data()

    def prepare_data(self):
        self.msgs = []
        self.counter = counter.Counter(
            'instance',
            counter.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='user-id',
            project_id='project-id',
            resource_id='resource-id',
            timestamp=datetime.datetime(2012, 7, 2, 10, 40),
            resource_metadata={'display_name': 'test-server',
                               'tag': 'self.counter',
                               }
        )
        self.msg1 = meter.meter_message_from_counter(self.counter,
                                                     cfg.CONF.metering_secret,
                                                     'test-1',
                                                     )
        self.conn.record_metering_data(self.msg1)
        self.msgs.append(self.msg1)

        self.counter2 = counter.Counter(
            'instance',
            counter.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='user-id',
            project_id='project-id',
            resource_id='resource-id-alternate',
            timestamp=datetime.datetime(2012, 7, 2, 10, 41),
            resource_metadata={'display_name': 'test-server',
                               'tag': 'self.counter2',
                               }
        )
        self.msg2 = meter.meter_message_from_counter(self.counter2,
                                                     cfg.CONF.metering_secret,
                                                     'test-2',
                                                     )
        self.conn.record_metering_data(self.msg2)
        self.msgs.append(self.msg2)

        self.counter3 = counter.Counter(
            'instance',
            counter.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='user-id-alternate',
            project_id='project-id',
            resource_id='resource-id-alternate',
            timestamp=datetime.datetime(2012, 7, 2, 10, 41),
            resource_metadata={'display_name': 'test-server',
                               'tag': 'self.counter3',
                               }
        )
        self.msg3 = meter.meter_message_from_counter(self.counter3,
                                                     cfg.CONF.metering_secret,
                                                     'test-3',
                                                     )
        self.conn.record_metering_data(self.msg3)
        self.msgs.append(self.msg3)

        for i in range(2, 4):
            c = counter.Counter(
                'instance',
                counter.TYPE_CUMULATIVE,
                unit='',
                volume=1,
                user_id='user-id-%s' % i,
                project_id='project-id-%s' % i,
                resource_id='resource-id-%s' % i,
                timestamp=datetime.datetime(2012, 7, 2, 10, 40 + i),
                resource_metadata={'display_name': 'test-server',
                                   'tag': 'counter-%s' % i},
            )
            msg = meter.meter_message_from_counter(c, cfg.CONF.metering_secret,
                                                   'test')
            self.conn.record_metering_data(msg)
            self.msgs.append(msg)

    def get_sources_by_user_id(self, id):
        return self.engine.get_sources_by_user_id(id)

    def get_sources_by_project_id(self, id):
        return self.engine.get_sources_by_project_id(id)


class UserTest(DBTestBase):

    def test_new_user(self):
        user_sources = self.get_sources_by_user_id('user-id')
        assert user_sources != []

    def test_new_user_source(self):
        user_sources = self.get_sources_by_user_id('user-id')
        assert set(user_sources) == set(['test-1', 'test-2'])

    def test_get_users(self):
        users = self.conn.get_users()
        assert set(users) == set(['user-id',
                                  'user-id-alternate',
                                  'user-id-2',
                                  'user-id-3',
                                  ])

    def test_get_users_by_source(self):
        users = self.conn.get_users(source='test-1')
        assert list(users) == ['user-id']


class ProjectTest(DBTestBase):

    def test_new_project(self):
        project_sources = self.get_sources_by_project_id('project-id')
        assert list(project_sources) != []

    def test_new_project_source(self):
        project_sources = self.get_sources_by_project_id('project-id')
        assert set(project_sources) == set(['test-1', 'test-2', 'test-3'])

    def test_get_projects(self):
        projects = self.conn.get_projects()
        expected = set(['project-id', 'project-id-2', 'project-id-3'])
        assert set(projects) == expected

    def test_get_projects_by_source(self):
        projects = self.conn.get_projects(source='test-1')
        expected = ['project-id']
        assert list(projects) == expected


class ResourceTest(DBTestBase):

    def test_get_resources(self):
        resources = list(self.conn.get_resources())
        assert len(resources) == 4
        for resource in resources:
            if resource['resource_id'] != 'resource-id':
                continue
            assert resource['resource_id'] == 'resource-id'
            assert resource['project_id'] == 'project-id'
            assert resource['user_id'] == 'user-id'
            assert resource['metadata']['display_name'] == 'test-server'
            foo = map(lambda x: [x['counter_name'],
                                 x['counter_type'],
                                 x['counter_unit']],
                      resource['meter'])
            assert ['instance', 'cumulative', ''] in foo
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
                                                 end_timestamp=end_ts))
        resource_ids = [r['resource_id'] for r in resources]
        assert set(resource_ids) == set(['resource-id-2'])

    def test_get_resources_by_source(self):
        resources = list(self.conn.get_resources(source='test-1'))
        assert len(resources) == 1
        ids = set(r['resource_id'] for r in resources)
        assert ids == set(['resource-id'])

    def test_get_resources_by_user(self):
        resources = list(self.conn.get_resources(user='user-id'))
        assert len(resources) == 2
        ids = set(r['resource_id'] for r in resources)
        assert ids == set(['resource-id', 'resource-id-alternate'])

    def test_get_resources_by_project(self):
        resources = list(self.conn.get_resources(project='project-id'))
        assert len(resources) == 2
        ids = set(r['resource_id'] for r in resources)
        assert ids == set(['resource-id', 'resource-id-alternate'])

    def test_get_resources_by_metaquery(self):
        q = {'metadata.display_name': 'test-server'}
        got_not_imp = False
        try:
            resources = list(self.conn.get_resources(metaquery=q))
            assert len(resources) == 4
        except NotImplementedError:
            got_not_imp = True
            self.assertTrue(got_not_imp)
        #this should work, but it doesn't.
        #actually unless I wrap get_resources in list()
        #it doesn't get called - weird
        #self.assertRaises(NotImplementedError,
        #                  self.conn.get_resources,
        #                  metaquery=q)

    def test_get_resources_by_empty_metaquery(self):
        resources = list(self.conn.get_resources(metaquery={}))
        self.assertTrue(len(resources) == 4)


class MeterTest(DBTestBase):

    def test_get_meters(self):
        results = list(self.conn.get_meters())
        assert len(results) == 4

    def test_get_meters_by_user(self):
        results = list(self.conn.get_meters(user='user-id'))
        assert len(results) == 1

    def test_get_meters_by_project(self):
        results = list(self.conn.get_meters(project='project-id'))
        assert len(results) == 2

    def test_get_meters_by_metaquery(self):
        q = {'metadata.display_name': 'test-server'}
        got_not_imp = False
        try:
            results = list(self.conn.get_meters(metaquery=q))
            assert results
            assert len(results) == 4
        except NotImplementedError:
            got_not_imp = True
            self.assertTrue(got_not_imp)

    def test_get_meters_by_empty_metaquery(self):
        results = list(self.conn.get_meters(metaquery={}))
        self.assertTrue(len(results) == 4)


class RawEventTest(DBTestBase):

    def test_get_samples_by_user(self):
        f = storage.EventFilter(user='user-id')
        results = list(self.conn.get_samples(f))
        assert len(results) == 2
        for meter in results:
            assert meter in [self.msg1, self.msg2]

    def test_get_samples_by_project(self):
        f = storage.EventFilter(project='project-id')
        results = list(self.conn.get_samples(f))
        assert results
        for meter in results:
            assert meter in [self.msg1, self.msg2, self.msg3]

    def test_get_samples_by_resource(self):
        f = storage.EventFilter(user='user-id', resource='resource-id')
        results = list(self.conn.get_samples(f))
        assert results
        meter = results[0]
        assert meter is not None
        assert meter == self.msg1

    def test_get_samples_by_metaquery(self):
        q = {'metadata.display_name': 'test-server'}
        f = storage.EventFilter(metaquery=q)
        got_not_imp = False
        try:
            results = list(self.conn.get_samples(f))
            assert results
            for meter in results:
                assert meter in self.msgs
        except NotImplementedError:
            got_not_imp = True
            self.assertTrue(got_not_imp)

    def test_get_samples_by_start_time(self):
        f = storage.EventFilter(
            user='user-id',
            start=datetime.datetime(2012, 7, 2, 10, 41),
        )
        results = list(self.conn.get_samples(f))
        assert len(results) == 1
        assert results[0]['timestamp'] == datetime.datetime(2012, 7, 2, 10, 41)

    def test_get_samples_by_end_time(self):
        f = storage.EventFilter(
            user='user-id',
            end=datetime.datetime(2012, 7, 2, 10, 41),
        )
        results = list(self.conn.get_samples(f))
        length = len(results)
        assert length == 1
        assert results[0]['timestamp'] == datetime.datetime(2012, 7, 2, 10, 40)

    def test_get_samples_by_both_times(self):
        f = storage.EventFilter(
            start=datetime.datetime(2012, 7, 2, 10, 42),
            end=datetime.datetime(2012, 7, 2, 10, 43),
        )
        results = list(self.conn.get_samples(f))
        length = len(results)
        assert length == 1
        assert results[0]['timestamp'] == datetime.datetime(2012, 7, 2, 10, 42)

    def test_get_samples_by_name(self):
        f = storage.EventFilter(user='user-id', meter='no-such-meter')
        results = list(self.conn.get_samples(f))
        assert not results

    def test_get_samples_by_name2(self):
        f = storage.EventFilter(user='user-id', meter='instance')
        results = list(self.conn.get_samples(f))
        assert results

    def test_get_samples_by_source(self):
        f = storage.EventFilter(source='test-1')
        results = list(self.conn.get_samples(f))
        assert results
        assert len(results) == 1


class SumTest(DBTestBase):

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


class TestGetEventInterval(DBTestBase):

    def setUp(self):
        super(TestGetEventInterval, self).setUp()

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
            resource='111',
            meter='instance',
            start=self.start,
            end=self.end,
        )

    def _make_events(self, *timestamps):
        for t in timestamps:
            c = counter.Counter(
                'instance',
                counter.TYPE_CUMULATIVE,
                '',
                1,
                '11',
                '1',
                '111',
                timestamp=t,
                resource_metadata={'display_name': 'test-server',
                                   }
            )
            msg = meter.meter_message_from_counter(c, cfg.CONF.metering_secret,
                                                   'test')
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


class MaxProjectTest(DBTestBase):

    def prepare_data(self):
        self.counters = []
        for i in range(3):
            c = counter.Counter(
                'volume.size',
                'gauge',
                'GiB',
                5 + i,
                'user-id',
                'project1',
                'resource-id-%s' % i,
                timestamp=datetime.datetime(2012, 9, 25, 10 + i, 30 + i),
                resource_metadata={'display_name': 'test-volume',
                                   'tag': 'self.counter',
                                   }
            )
            self.counters.append(c)
            msg = meter.meter_message_from_counter(c,
                                                   cfg.CONF.metering_secret,
                                                   'source1',
                                                   )
            self.conn.record_metering_data(msg)

    def test_no_bounds(self):
        expected = [{'value': 5.0, 'resource_id': u'resource-id-0'},
                    {'value': 6.0, 'resource_id': u'resource-id-1'},
                    {'value': 7.0, 'resource_id': u'resource-id-2'}]

        f = storage.EventFilter(project='project1',
                                meter='volume.size')

        results = list(self.conn.get_volume_max(f))
        assert results == expected

    def test_start_timestamp(self):
        expected = [{'value': 6L, 'resource_id': u'resource-id-1'},
                    {'value': 7L, 'resource_id': u'resource-id-2'}]

        f = storage.EventFilter(project='project1',
                                meter='volume.size',
                                start='2012-09-25T11:30:00')

        results = list(self.conn.get_volume_max(f))
        assert results == expected

    def test_start_timestamp_after(self):
        f = storage.EventFilter(project='project1',
                                meter='volume.size',
                                start='2012-09-25T12:34:00')

        results = list(self.conn.get_volume_max(f))
        assert results == []

    def test_end_timestamp(self):
        expected = [{'value': 5L, 'resource_id': u'resource-id-0'}]

        f = storage.EventFilter(project='project1',
                                meter='volume.size',
                                end='2012-09-25T11:30:00')

        results = list(self.conn.get_volume_max(f))
        assert results == expected

    def test_end_timestamp_before(self):
        f = storage.EventFilter(project='project1',
                                meter='volume.size',
                                end='2012-09-25T09:54:00')

        results = list(self.conn.get_volume_max(f))
        assert results == []

    def test_start_end_timestamp(self):
        expected = [{'value': 6L, 'resource_id': u'resource-id-1'}]

        f = storage.EventFilter(project='project1',
                                meter='volume.size',
                                start='2012-09-25T11:30:00',
                                end='2012-09-25T11:32:00')

        results = list(self.conn.get_volume_max(f))
        assert results == expected


class MaxResourceTest(DBTestBase):

    def prepare_data(self):
        self.counters = []
        for i in range(3):
            c = counter.Counter(
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
                                   }
            )
            self.counters.append(c)
            msg = meter.meter_message_from_counter(c,
                                                   cfg.CONF.metering_secret,
                                                   'source1',
                                                   )
            self.conn.record_metering_data(msg)

    def test_no_bounds(self):
        expected = [{'value': 7L, 'resource_id': u'resource-id'}]

        f = storage.EventFilter(resource='resource-id',
                                meter='volume.size')

        results = list(self.conn.get_volume_max(f))
        assert results == expected

    def test_start_timestamp(self):
        expected = [{'value': 7L, 'resource_id': u'resource-id'}]

        f = storage.EventFilter(resource='resource-id',
                                meter='volume.size',
                                start='2012-09-25T11:30:00')

        results = list(self.conn.get_volume_max(f))
        assert results == expected

    def test_start_timestamp_after(self):
        f = storage.EventFilter(resource='resource-id',
                                meter='volume.size',
                                start='2012-09-25T12:34:00')

        results = list(self.conn.get_volume_max(f))
        assert results == []

    def test_end_timestamp(self):
        expected = [{'value': 5L, 'resource_id': u'resource-id'}]

        f = storage.EventFilter(resource='resource-id',
                                meter='volume.size',
                                end='2012-09-25T11:30:00')

        results = list(self.conn.get_volume_max(f))
        assert results == expected

    def test_end_timestamp_before(self):
        f = storage.EventFilter(resource='resource-id',
                                meter='volume.size',
                                end='2012-09-25T09:54:00')

        results = list(self.conn.get_volume_max(f))
        assert results == []

    def test_start_end_timestamp(self):
        expected = [{'value': 6L, 'resource_id': u'resource-id'}]

        f = storage.EventFilter(resource='resource-id',
                                meter='volume.size',
                                start='2012-09-25T11:30:00',
                                end='2012-09-25T11:32:00')

        results = list(self.conn.get_volume_max(f))
        assert results == expected


class StatisticsTest(DBTestBase):

    def prepare_data(self):
        self.counters = []
        for i in range(3):
            c = counter.Counter(
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
                                   }
            )
            self.counters.append(c)
            msg = meter.meter_message_from_counter(c,
                                                   secret='not-so-secret',
                                                   source='test',
                                                   )
            self.conn.record_metering_data(msg)
        for i in range(3):
            c = counter.Counter(
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
                                   }
            )
            self.counters.append(c)
            msg = meter.meter_message_from_counter(c,
                                                   secret='not-so-secret',
                                                   source='test',
                                                   )
            self.conn.record_metering_data(msg)

    def test_by_user(self):
        f = storage.EventFilter(
            user='user-5',
            meter='volume.size',
        )
        results = self.conn.get_meter_statistics(f)[0]
        self.assertEqual(results['duration'],
                         (datetime.datetime(2012, 9, 25, 12, 32)
                          - datetime.datetime(2012, 9, 25, 10, 30)).seconds)
        assert results['count'] == 3
        assert results['min'] == 8
        assert results['max'] == 10
        assert results['sum'] == 27
        assert results['avg'] == 9

    def test_no_period_in_query(self):
        f = storage.EventFilter(
            user='user-5',
            meter='volume.size',
        )
        results = self.conn.get_meter_statistics(f)[0]
        assert results['period'] == 0

    def test_period_is_int(self):
        f = storage.EventFilter(
            meter='volume.size',
        )
        results = self.conn.get_meter_statistics(f)[0]
        assert(isinstance(results['period'], int))
        assert results['count'] == 6

    def test_by_user_period(self):
        f = storage.EventFilter(
            user='user-5',
            meter='volume.size',
            start='2012-09-25T10:28:00',
        )
        results = self.conn.get_meter_statistics(f, period=7200)
        self.assertEqual(len(results), 2)
        self.assertEqual(set(r['period_start'] for r in results),
                         set([datetime.datetime(2012, 9, 25, 10, 28),
                              datetime.datetime(2012, 9, 25, 12, 28)]))
        self.assertEqual(set(r['period_end'] for r in results),
                         set([datetime.datetime(2012, 9, 25, 12, 28),
                              datetime.datetime(2012, 9, 25, 14, 28)]))
        r = results[0]
        self.assertEqual(r['period_start'],
                         datetime.datetime(2012, 9, 25, 10, 28))
        self.assertEqual(r['count'], 2)
        self.assertEqual(r['avg'], 8.5)
        self.assertEqual(r['min'], 8)
        self.assertEqual(r['max'], 9)
        self.assertEqual(r['sum'], 17)
        self.assertEqual(r['period'], 7200)
        self.assertIsInstance(r['period'], int)
        expected_end = r['period_start'] + datetime.timedelta(seconds=7200)
        self.assertEqual(r['period_end'], expected_end)
        self.assertEqual(r['duration'], 3660)
        self.assertEqual(r['duration_start'],
                         datetime.datetime(2012, 9, 25, 10, 30))
        self.assertEqual(r['duration_end'],
                         datetime.datetime(2012, 9, 25, 11, 31))

    def test_by_user_period_start_end(self):
        f = storage.EventFilter(
            user='user-5',
            meter='volume.size',
            start='2012-09-25T10:28:00',
            end='2012-09-25T11:28:00',
        )
        results = self.conn.get_meter_statistics(f, period=1800)
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r['period_start'],
                         datetime.datetime(2012, 9, 25, 10, 28))
        self.assertEqual(r['count'], 1)
        self.assertEqual(r['avg'], 8)
        self.assertEqual(r['min'], 8)
        self.assertEqual(r['max'], 8)
        self.assertEqual(r['sum'], 8)
        self.assertEqual(r['period'], 1800)
        self.assertEqual(r['period_end'],
                         r['period_start']
                         + datetime.timedelta(seconds=1800))
        self.assertEqual(r['duration'], 0)
        self.assertEqual(r['duration_start'],
                         datetime.datetime(2012, 9, 25, 10, 30))
        self.assertEqual(r['duration_end'],
                         datetime.datetime(2012, 9, 25, 10, 30))

    def test_by_project(self):
        f = storage.EventFilter(
            meter='volume.size',
            resource='resource-id',
            start='2012-09-25T11:30:00',
            end='2012-09-25T11:32:00',
        )
        results = self.conn.get_meter_statistics(f)[0]
        self.assertEqual(results['duration'], 0)
        assert results['count'] == 1
        assert results['min'] == 6
        assert results['max'] == 6
        assert results['sum'] == 6
        assert results['avg'] == 6

    def test_one_resource(self):
        f = storage.EventFilter(
            user='user-id',
            meter='volume.size',
        )
        results = self.conn.get_meter_statistics(f)[0]
        self.assertEqual(results['duration'],
                         (datetime.datetime(2012, 9, 25, 12, 32)
                          - datetime.datetime(2012, 9, 25, 10, 30)).seconds)
        assert results['count'] == 3
        assert results['min'] == 5
        assert results['max'] == 7
        assert results['sum'] == 18
        assert results['avg'] == 6
