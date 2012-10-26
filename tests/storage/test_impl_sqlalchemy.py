# -*- encoding: utf-8 -*-
#
# Author: John Tran <jhtran@att.com>
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
"""Tests for ceilometer/storage/impl_sqlalchemy.py
"""

import datetime
import logging
import os
import re
import sqlalchemy
import unittest

from ceilometer import counter
from ceilometer import meter
from ceilometer import storage
from ceilometer.storage import migration
from ceilometer.openstack.common import cfg
from ceilometer.storage import impl_sqlalchemy
from ceilometer.storage.sqlalchemy.models import Meter, Project, Resource
from ceilometer.storage.sqlalchemy.models import User


LOG = logging.getLogger(__name__)
CEILOMETER_TEST_LIVE = bool(int(os.environ.get('CEILOMETER_TEST_LIVE', 0)))
if CEILOMETER_TEST_LIVE:
    MYSQL_DBNAME = 'ceilometer_test'
    MYSQL_BASE_URL = 'mysql://ceilometer:somepass@localhost/'
    MYSQL_URL = MYSQL_BASE_URL + MYSQL_DBNAME


class Connection(impl_sqlalchemy.Connection):

    def _get_connection(self, conf):
        try:
            return super(Connection, self)._get_connection(conf)
        except:
            LOG.debug('Unable to connect to %s' % conf.database_connection)
            raise


class SQLAlchemyEngineSubBase(unittest.TestCase):

    def tearDown(self):
        super(SQLAlchemyEngineSubBase, self).tearDown()
        engine_conn = self.session.bind.connect()
        if CEILOMETER_TEST_LIVE:
            engine_conn.execute('drop database %s' % MYSQL_DBNAME)
            engine_conn.execute('create database %s' % MYSQL_DBNAME)
        # needed for sqlite in-memory db to destroy
        self.session.close_all()
        self.session.bind.dispose()

    def setUp(self):
        super(SQLAlchemyEngineSubBase, self).setUp()

        self.conf = cfg.CONF
        self.conf.database_connection = 'sqlite://'
        # Use a real MySQL server if we can connect, but fall back
        # to a Sqlite in-memory connection if we cannot.
        if CEILOMETER_TEST_LIVE:
            # should pull from conf file but for now manually specified
            # just make sure ceilometer_test db exists in mysql
            self.conf.database_connection = MYSQL_URL
            engine = sqlalchemy.create_engine(MYSQL_BASE_URL)
            engine_conn = engine.connect()
            try:
                engine_conn.execute('drop database %s' % MYSQL_DBNAME)
            except sqlalchemy.exc.OperationalError:
                pass
            engine_conn.execute('create database %s' % MYSQL_DBNAME)

        self.conn = Connection(self.conf)
        self.session = self.conn.session

        migration.db_sync()


class SQLAlchemyEngineTestBase(SQLAlchemyEngineSubBase):

    def tearDown(self):
        super(SQLAlchemyEngineTestBase, self).tearDown()

    def setUp(self):
        super(SQLAlchemyEngineTestBase, self).setUp()

        self.counter = counter.Counter(
            'instance',
            counter.TYPE_CUMULATIVE,
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

        self.counter2 = counter.Counter(
            'instance',
            counter.TYPE_CUMULATIVE,
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

        self.counter3 = counter.Counter(
            'instance',
            counter.TYPE_CUMULATIVE,
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

        for i in range(2, 4):
            c = counter.Counter(
                'instance',
                counter.TYPE_CUMULATIVE,
                1,
                'user-id-%s' % i,
                'project-id-%s' % i,
                'resource-id-%s' % i,
                timestamp=datetime.datetime(2012, 7, 2, 10, 40 + i),
                resource_metadata={'display_name': 'test-server',
                                   'tag': 'counter-%s' % i,
                                  }
                )
            msg = meter.meter_message_from_counter(c, cfg.CONF.metering_secret,
                                                   'test')
            self.conn.record_metering_data(msg)


class UserTest(SQLAlchemyEngineTestBase):

    def test_new_user(self):
        user = self.session.query(User).get('user-id')
        assert user is not None

    def test_new_user_source(self):
        user = self.session.query(User).get('user-id')
        assert hasattr(user, 'sources')
        assert map(lambda x: x.id, user.sources) == ['test-1', 'test-2']

    def test_get_users(self):
        xpct = set(['user-id', 'user-id-alternate', 'user-id-2', 'user-id-3'])
        assert set(self.conn.get_users()) == xpct

    def test_get_users_by_source(self):
        assert set(self.conn.get_users(source='test-1')) == set(['user-id'])


class ProjectTest(SQLAlchemyEngineTestBase):

    def test_new_project(self):
        project = self.session.query(Project).get('project-id')
        assert project is not None

    def test_new_project_source(self):
        project = self.session.query(Project).get('project-id')
        assert hasattr(project, 'sources')
        expected = ['test-1', 'test-2', 'test-3']
        assert map(lambda x: x.id, project.sources) == expected

    def test_get_projects(self):
        projects = self.session.query(Project).all()
        projects = map(lambda x: x.id, projects)
        expect = set(['project-id', 'project-id-2', 'project-id-3'])
        assert set(projects) == expect

    def test_get_projects_by_source(self):
        projects = self.conn.get_projects(source='test-1')
        assert list(projects) == ['project-id']


class ResourceTest(SQLAlchemyEngineTestBase):

    def test_new_resource(self):
        resource = self.session.query(Resource).get('resource-id')
        assert resource is not None

    def test_new_resource_project(self):
        resource = self.session.query(Resource).get('resource-id')
        assert hasattr(resource, 'project')
        assert resource.project.id == 'project-id'

    def test_new_resource_user(self):
        resource = self.session.query(Resource).get('resource-id')
        assert hasattr(resource, 'user')
        assert resource.user.id == 'user-id'

    def test_new_resource_meter(self):
        resource = self.session.query(Resource).filter_by(id='resource-id').\
                       filter(Meter.counter_name == 'instance').\
                       filter(Meter.counter_type == 'cumulative').first()
        assert len(set(resource.meters)) == 1
        foo = map(lambda x: [x.counter_name, x.counter_type], resource.meters)
        assert ['instance', 'cumulative'] in foo

    def test_new_resource_metadata(self):
        resource = self.session.query(Resource).get('resource-id')
        assert hasattr(resource, 'metadata')
        metadata = resource.resource_metadata
        assert metadata['display_name'] == 'test-server'

    def test_get_resources(self):
        resources = list(self.conn.get_resources())
        assert len(resources) == 4
        for resource in resources:
            if resource['resource_id'] != 'resource-id':
                continue
            assert resource['resource_id'] == 'resource-id'
            assert resource['project_id'] == 'project-id'
            assert resource['user_id'] == 'user-id'
            assert 'resource_metadata' in resource
            assert 'meters' in resource
            foo = map(lambda x: [x['counter_name'], x['counter_type']],
                      resource['meters'])
            assert ['instance', 'cumulative'] in foo
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
        assert set(resource_ids) == set(['resource-id-2'])

    def test_get_resources_by_source(self):
        resources = list(self.conn.get_resources(source='test-1'))
        assert len(resources) == 1
        ids = set(r['resource_id'] for r in resources)
        assert ids == set(['resource-id'])

    def test_get_resources_by_user(self):
        resources = list(self.conn.get_resources(user='user-id'))
        assert len(resources) == 1
        ids = set(r['resource_id'] for r in resources)
        assert ids == set(['resource-id'])

    def test_get_resources_by_project(self):
        resources = list(self.conn.get_resources(project='project-id'))
        assert len(resources) == 2
        ids = set(r['resource_id'] for r in resources)
        assert ids == set(['resource-id', 'resource-id-alternate'])


class MeterTest(SQLAlchemyEngineTestBase):

    def _compare_raw(self, msg_dict, result_dict):
        for k, v in msg_dict.items():
            if k in ['timestamp', 'source']:
                continue
            if k == 'resource_metadata':
                key = result_dict[k]
                value = v
            else:
                key = str(result_dict[k])
                value = str(v)
            assert key == value

    def _iterate_msgs(self, results):
        for meter in results:
            labels = map(lambda x: x['id'], meter['sources'])
            # should only have one source
            assert len(labels) == 1
            count = re.match('test-(\d+)', labels[0]).group(1)
            self._compare_raw(getattr(self, 'msg' + count), meter)

    def test_new_meter(self):
        meter = self.session.query(Meter).first()
        assert meter is not None

    def test_get_raw_events_by_user(self):
        f = storage.EventFilter(user='user-id')
        results = list(self.conn.get_raw_events(f))
        assert len(results) == 2
        self._iterate_msgs(results)

    def test_get_raw_events_by_project(self):
        f = storage.EventFilter(project='project-id')
        results = list(self.conn.get_raw_events(f))
        assert len(results) == 3
        self._iterate_msgs(results)

    def test_get_raw_events_by_resource(self):
        f = storage.EventFilter(user='user-id', resource='resource-id')
        results = list(self.conn.get_raw_events(f))
        assert len(results) == 1
        self._compare_raw(self.msg1, results[0])

    def test_get_raw_events_by_start_time(self):
        f = storage.EventFilter(
            user='user-id',
            start=datetime.datetime(2012, 7, 2, 10, 41),
            )
        results = list(self.conn.get_raw_events(f))
        assert len(results) == 1
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
        f = storage.EventFilter(user='user-id', meter='no-such-meter')
        results = list(self.conn.get_raw_events(f))
        assert not results

    def test_get_raw_events_by_meter2(self):
        f = storage.EventFilter(user='user-id', meter='instance')
        results = list(self.conn.get_raw_events(f))
        assert results


class TestGetEventInterval(SQLAlchemyEngineTestBase):

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


class SumTest(SQLAlchemyEngineTestBase):

    def setUp(self):
        super(SumTest, self).setUp()

    def test_by_user(self):
        f = storage.EventFilter(
            user='user-id',
            meter='instance',
            )
        results = list(self.conn.get_volume_sum(f))
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


class MaxProjectTest(SQLAlchemyEngineSubBase):

    def setUp(self):
        super(MaxProjectTest, self).setUp()

        self.counters = []
        for i in range(3):
            c = counter.Counter(
                'volume.size',
                'gauge',
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

        f = storage.EventFilter(project='project1')

        results = list(self.conn.get_volume_max(f))
        assert results == expected

    def test_start_timestamp(self):
        expected = [{'value': 6L, 'resource_id': u'resource-id-1'},
                    {'value': 7L, 'resource_id': u'resource-id-2'}]

        f = storage.EventFilter(project='project1',
                                start='2012-09-25T11:30:00')

        results = list(self.conn.get_volume_max(f))
        assert results == expected

    def test_start_timestamp_after(self):
        f = storage.EventFilter(project='project1',
                                start='2012-09-25T12:34:00')

        results = list(self.conn.get_volume_max(f))
        assert results == []

    def test_end_timestamp(self):
        expected = [{'value': 5L, 'resource_id': u'resource-id-0'}]

        f = storage.EventFilter(project='project1', end='2012-09-25T11:30:00')

        results = list(self.conn.get_volume_max(f))
        assert results == expected

    def test_end_timestamp_before(self):
        f = storage.EventFilter(project='project1', end='2012-09-25T09:54:00')

        results = list(self.conn.get_volume_max(f))
        assert results == []

    def test_start_end_timestamp(self):
        expected = [{'value': 6L, 'resource_id': u'resource-id-1'}]

        f = storage.EventFilter(project='project1',
                                start='2012-09-25T11:30:00',
                                end='2012-09-25T11:32:00')

        results = list(self.conn.get_volume_max(f))
        assert results == expected


class MaxResourceTest(SQLAlchemyEngineSubBase):

    def setUp(self):
        super(MaxResourceTest, self).setUp()

        self.counters = []
        for i in range(3):
            c = counter.Counter(
                'volume.size',
                'gauge',
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

        f = storage.EventFilter(resource='resource-id')

        results = list(self.conn.get_volume_max(f))
        assert results == expected

    def test_start_timestamp(self):
        expected = [{'value': 7L, 'resource_id': u'resource-id'}]

        f = storage.EventFilter(resource='resource-id',
                                start='2012-09-25T11:30:00')

        results = list(self.conn.get_volume_max(f))
        assert results == expected

    def test_start_timestamp_after(self):
        f = storage.EventFilter(resource='resource-id',
                                start='2012-09-25T12:34:00')

        results = list(self.conn.get_volume_max(f))
        assert results == []

    def test_end_timestamp(self):
        expected = [{'value': 5L, 'resource_id': u'resource-id'}]

        f = storage.EventFilter(resource='resource-id',
                                end='2012-09-25T11:30:00')

        results = list(self.conn.get_volume_max(f))
        assert results == expected

    def test_end_timestamp_before(self):
        f = storage.EventFilter(resource='resource-id',
                                end='2012-09-25T09:54:00')

        results = list(self.conn.get_volume_max(f))
        assert results == []

    def test_start_end_timestamp(self):
        expected = [{'value': 6L, 'resource_id': u'resource-id'}]

        f = storage.EventFilter(resource='resource-id',
                                start='2012-09-25T11:30:00',
                                end='2012-09-25T11:32:00')

        results = list(self.conn.get_volume_max(f))
        assert results == expected
