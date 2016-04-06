#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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
"""Test events statistics retrieval."""

import datetime

from ceilometer.publisher import utils
from ceilometer import sample
from ceilometer.tests import db as tests_db
from ceilometer.tests.functional.api import v2


class TestMaxProjectVolume(v2.FunctionalTest):
    PATH = '/meters/volume.size/statistics'

    def setUp(self):
        super(TestMaxProjectVolume, self).setUp()
        for i in range(3):
            s = sample.Sample(
                'volume.size',
                'gauge',
                'GiB',
                5 + i,
                'user-id',
                'project1',
                'resource-id-%s' % i,
                timestamp=datetime.datetime(2012, 9, 25, 10 + i, 30 + i),
                resource_metadata={'display_name': 'test-volume',
                                   'tag': 'self.sample',
                                   },
                source='source1',
            )
            msg = utils.meter_message_from_counter(
                s, self.CONF.publisher.telemetry_secret,
            )
            self.conn.record_metering_data(msg)

    def test_no_time_bounds(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            }])
        self.assertEqual(7, data[0]['max'])
        self.assertEqual(3, data[0]['count'])

    def test_start_timestamp(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'ge',
                                            'value': '2012-09-25T11:30:00',
                                            },
                                           ])
        self.assertEqual(7, data[0]['max'])
        self.assertEqual(2, data[0]['count'])

    def test_start_timestamp_after(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'ge',
                                            'value': '2012-09-25T12:34:00',
                                            },
                                           ])
        self.assertEqual([], data)

    def test_end_timestamp(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'le',
                                            'value': '2012-09-25T11:30:00',
                                            },
                                           ])
        self.assertEqual(5, data[0]['max'])
        self.assertEqual(1, data[0]['count'])

    def test_end_timestamp_before(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'le',
                                            'value': '2012-09-25T09:54:00',
                                            },
                                           ])
        self.assertEqual([], data)

    def test_start_end_timestamp(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'ge',
                                            'value': '2012-09-25T11:30:00',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'le',
                                            'value': '2012-09-25T11:32:00',
                                            },
                                           ])
        self.assertEqual(6, data[0]['max'])
        self.assertEqual(1, data[0]['count'])


class TestMaxResourceVolume(v2.FunctionalTest):
    PATH = '/meters/volume.size/statistics'

    def setUp(self):
        super(TestMaxResourceVolume, self).setUp()
        for i in range(3):
            s = sample.Sample(
                'volume.size',
                'gauge',
                'GiB',
                5 + i,
                'user-id',
                'project1',
                'resource-id',
                timestamp=datetime.datetime(2012, 9, 25, 10 + i, 30 + i),
                resource_metadata={'display_name': 'test-volume',
                                   'tag': 'self.sample',
                                   },
                source='source1',
            )
            msg = utils.meter_message_from_counter(
                s, self.CONF.publisher.telemetry_secret,
            )
            self.conn.record_metering_data(msg)

    def test_no_time_bounds(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            }])
        self.assertEqual(7, data[0]['max'])
        self.assertEqual(3, data[0]['count'])

    def test_no_time_bounds_with_period(self):
        data = self.get_json(self.PATH,
                             q=[{'field': 'resource_id',
                                 'value': 'resource-id'}],
                             period=3600)
        self.assertEqual(3, len(data))
        self.assertEqual(set([u'2012-09-25T10:30:00',
                              u'2012-09-25T12:32:00',
                              u'2012-09-25T11:31:00']),
                         set(x['duration_start'] for x in data))
        self.assertEqual(3600, data[0]['period'])
        self.assertEqual(set([u'2012-09-25T10:30:00',
                              u'2012-09-25T11:30:00',
                              u'2012-09-25T12:30:00']),
                         set(x['period_start'] for x in data))

    def test_period_with_negative_value(self):
        resp = self.get_json(self.PATH, expect_errors=True,
                             q=[{'field': 'resource_id',
                                 'value': 'resource-id'}],
                             period=-1)
        self.assertEqual(400, resp.status_code)

    @tests_db.run_with('sqlite', 'mysql', 'pgsql', 'hbase')
    def test_period_with_large_value(self):
        resp = self.get_json(self.PATH, expect_errors=True,
                             q=[{'field': 'user_id',
                                 'value': 'user-id'}],
                             period=10000000000000)
        self.assertEqual(400, resp.status_code)
        self.assertIn(b"Invalid period", resp.body)

    def test_start_timestamp(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'ge',
                                            'value': '2012-09-25T11:30:00',
                                            },
                                           ])
        self.assertEqual(7, data[0]['max'])
        self.assertEqual(2, data[0]['count'])

    def test_start_timestamp_after(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'ge',
                                            'value': '2012-09-25T12:34:00',
                                            },
                                           ])
        self.assertEqual([], data)

    def test_end_timestamp(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'le',
                                            'value': '2012-09-25T11:30:00',
                                            },
                                           ])
        self.assertEqual(5, data[0]['max'])
        self.assertEqual(1, data[0]['count'])

    def test_end_timestamp_before(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'le',
                                            'value': '2012-09-25T09:54:00',
                                            },
                                           ])
        self.assertEqual([], data)

    def test_start_end_timestamp(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'ge',
                                            'value': '2012-09-25T11:30:00',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'le',
                                            'value': '2012-09-25T11:32:00',
                                            },
                                           ])
        self.assertEqual(6, data[0]['max'])
        self.assertEqual(1, data[0]['count'])


class TestSumProjectVolume(v2.FunctionalTest):

    PATH = '/meters/volume.size/statistics'

    def setUp(self):
        super(TestSumProjectVolume, self).setUp()
        for i in range(3):
            s = sample.Sample(
                'volume.size',
                'gauge',
                'GiB',
                5 + i,
                'user-id',
                'project1',
                'resource-id-%s' % i,
                timestamp=datetime.datetime(2012, 9, 25, 10 + i, 30 + i),
                resource_metadata={'display_name': 'test-volume',
                                   'tag': 'self.sample',
                                   },
                source='source1',
            )
            msg = utils.meter_message_from_counter(
                s, self.CONF.publisher.telemetry_secret,
            )
            self.conn.record_metering_data(msg)

    def test_no_time_bounds(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            }])
        expected = 5 + 6 + 7
        self.assertEqual(expected, data[0]['sum'])
        self.assertEqual(3, data[0]['count'])

    def test_start_timestamp(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'ge',
                                            'value': '2012-09-25T11:30:00',
                                            },
                                           ])
        expected = 6 + 7
        self.assertEqual(expected, data[0]['sum'])
        self.assertEqual(2, data[0]['count'])

    def test_start_timestamp_after(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'ge',
                                            'value': '2012-09-25T12:34:00',
                                            },
                                           ])
        self.assertEqual([], data)

    def test_end_timestamp(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'le',
                                            'value': '2012-09-25T11:30:00',
                                            },
                                           ])
        self.assertEqual(5, data[0]['sum'])
        self.assertEqual(1, data[0]['count'])

    def test_end_timestamp_before(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'le',
                                            'value': '2012-09-25T09:54:00',
                                            },
                                           ])
        self.assertEqual([], data)

    def test_start_end_timestamp(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'ge',
                                            'value': '2012-09-25T11:30:00',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'le',
                                            'value': '2012-09-25T11:32:00',
                                            },
                                           ])
        self.assertEqual(6, data[0]['sum'])
        self.assertEqual(1, data[0]['count'])


class TestSumResourceVolume(v2.FunctionalTest):

    PATH = '/meters/volume.size/statistics'

    def setUp(self):
        super(TestSumResourceVolume, self).setUp()
        for i in range(3):
            s = sample.Sample(
                'volume.size',
                'gauge',
                'GiB',
                5 + i,
                'user-id',
                'project1',
                'resource-id',
                timestamp=datetime.datetime(2012, 9, 25, 10 + i, 30 + i),
                resource_metadata={'display_name': 'test-volume',
                                   'tag': 'self.sample',
                                   },
                source='source1',
            )
            msg = utils.meter_message_from_counter(
                s, self.CONF.publisher.telemetry_secret,
            )
            self.conn.record_metering_data(msg)

    def test_no_time_bounds(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            }])
        self.assertEqual(5 + 6 + 7, data[0]['sum'])
        self.assertEqual(3, data[0]['count'])

    def test_no_time_bounds_with_period(self):
        data = self.get_json(self.PATH,
                             q=[{'field': 'resource_id',
                                 'value': 'resource-id'}],
                             period=1800)
        self.assertEqual(3, len(data))
        self.assertEqual(set([u'2012-09-25T10:30:00',
                              u'2012-09-25T12:32:00',
                              u'2012-09-25T11:31:00']),
                         set(x['duration_start'] for x in data))
        self.assertEqual(1800, data[0]['period'])
        self.assertEqual(set([u'2012-09-25T10:30:00',
                              u'2012-09-25T11:30:00',
                              u'2012-09-25T12:30:00']),
                         set(x['period_start'] for x in data))

    def test_start_timestamp(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'ge',
                                            'value': '2012-09-25T11:30:00',
                                            }])
        self.assertEqual(6 + 7, data[0]['sum'])
        self.assertEqual(2, data[0]['count'])

    def test_start_timestamp_with_period(self):
        data = self.get_json(self.PATH,
                             q=[{'field': 'resource_id',
                                 'value': 'resource-id'},
                                {'field': 'timestamp',
                                 'op': 'ge',
                                 'value': '2012-09-25T10:15:00'}],
                             period=7200)
        self.assertEqual(2, len(data))
        self.assertEqual(set([u'2012-09-25T10:30:00',
                              u'2012-09-25T12:32:00']),
                         set(x['duration_start'] for x in data))
        self.assertEqual(7200, data[0]['period'])
        self.assertEqual(set([u'2012-09-25T10:15:00',
                              u'2012-09-25T12:15:00']),
                         set(x['period_start'] for x in data))

    def test_start_timestamp_after(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'ge',
                                            'value': '2012-09-25T12:34:00',
                                            }])
        self.assertEqual([], data)

    def test_end_timestamp(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'le',
                                            'value': '2012-09-25T11:30:00',
                                            }])
        self.assertEqual(5, data[0]['sum'])
        self.assertEqual(1, data[0]['count'])

    def test_end_timestamp_before(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'le',
                                            'value': '2012-09-25T09:54:00',
                                            }])
        self.assertEqual([], data)

    def test_start_end_timestamp(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'ge',
                                            'value': '2012-09-25T11:30:00',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'lt',
                                            'value': '2012-09-25T11:32:00',
                                            }])
        self.assertEqual(6, data[0]['sum'])
        self.assertEqual(1, data[0]['count'])


class TestGroupByInstance(v2.FunctionalTest):

    PATH = '/meters/instance/statistics'

    def setUp(self):
        super(TestGroupByInstance, self).setUp()

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
            msg = utils.meter_message_from_counter(
                c, self.CONF.publisher.telemetry_secret,
            )
            self.conn.record_metering_data(msg)

    def test_group_by_user(self):
        data = self.get_json(self.PATH, groupby=['user_id'])
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(set(['user_id']), groupby_keys_set)
        self.assertEqual(set(['user-1', 'user-2', 'user-3']), groupby_vals_set)

        for r in data:
            grp = r['groupby']
            if grp == {'user_id': 'user-1'}:
                self.assertEqual(2, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(2, r['min'])
                self.assertEqual(2, r['max'])
                self.assertEqual(4, r['sum'])
                self.assertEqual(2, r['avg'])
            elif grp == {'user_id': 'user-2'}:
                self.assertEqual(4, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(1, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(8, r['sum'])
                self.assertEqual(2, r['avg'])
            elif grp == {'user_id': 'user-3'}:
                self.assertEqual(1, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(4, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(4, r['sum'])
                self.assertEqual(4, r['avg'])

    def test_group_by_resource(self):
        data = self.get_json(self.PATH, groupby=['resource_id'])
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(set(['resource_id']), groupby_keys_set)
        self.assertEqual(set(['resource-1', 'resource-2', 'resource-3']),
                         groupby_vals_set)

        for r in data:
            grp = r['groupby']
            if grp == {'resource_id': 'resource-1'}:
                self.assertEqual(3, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(2, r['min'])
                self.assertEqual(2, r['max'])
                self.assertEqual(6, r['sum'])
                self.assertEqual(2, r['avg'])
            elif grp == {'resource_id': 'resource-2'}:
                self.assertEqual(3, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(1, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(6, r['sum'])
                self.assertEqual(2, r['avg'])
            elif grp == {'resource_id': 'resource-3'}:
                self.assertEqual(1, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(4, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(4, r['sum'])
                self.assertEqual(4, r['avg'])

    def test_group_by_project(self):
        data = self.get_json(self.PATH, groupby=['project_id'])
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(set(['project_id']), groupby_keys_set)
        self.assertEqual(set(['project-1', 'project-2']), groupby_vals_set)

        for r in data:
            grp = r['groupby']
            if grp == {'project_id': 'project-1'}:
                self.assertEqual(5, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(1, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(10, r['sum'])
                self.assertEqual(2, r['avg'])
            elif grp == {'project_id': 'project-2'}:
                self.assertEqual(2, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(2, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(6, r['sum'])
                self.assertEqual(3, r['avg'])

    def test_group_by_unknown_field(self):
        response = self.get_json(self.PATH,
                                 expect_errors=True,
                                 groupby=['wtf'])
        self.assertEqual(400, response.status_code)

    def test_group_by_multiple_regular(self):
        data = self.get_json(self.PATH, groupby=['user_id', 'resource_id'])
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(set(['user_id', 'resource_id']), groupby_keys_set)
        self.assertEqual(set(['user-1', 'user-2', 'user-3', 'resource-1',
                              'resource-2', 'resource-3']),
                         groupby_vals_set)

        for r in data:
            grp = r['groupby']
            if grp == {'user_id': 'user-1',
                                  'resource_id': 'resource-1'}:
                self.assertEqual(2, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(2, r['min'])
                self.assertEqual(2, r['max'])
                self.assertEqual(4, r['sum'])
                self.assertEqual(2, r['avg'])
            elif grp == {'user_id': 'user-2',
                         'resource_id': 'resource-1'}:
                self.assertEqual(1, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(2, r['min'])
                self.assertEqual(2, r['max'])
                self.assertEqual(2, r['sum'])
                self.assertEqual(2, r['avg'])
            elif grp == {'user_id': 'user-2',
                         'resource_id': 'resource-2'}:
                self.assertEqual(3, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(1, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(6, r['sum'])
                self.assertEqual(2, r['avg'])
            elif grp == {'user_id': 'user-3',
                         'resource_id': 'resource-3'}:
                self.assertEqual(1, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(4, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(4, r['sum'])
                self.assertEqual(4, r['avg'])
            else:
                self.assertNotEqual(grp, {'user_id': 'user-1',
                                          'resource_id': 'resource-2'})
                self.assertNotEqual(grp, {'user_id': 'user-1',
                                          'resource_id': 'resource-3'})
                self.assertNotEqual(grp, {'user_id': 'user-2',
                                          'resource_id': 'resource-3'})
                self.assertNotEqual(grp, {'user_id': 'user-3',
                                          'resource_id': 'resource-1'})
                self.assertNotEqual(grp, {'user_id': 'user-3',
                                          'resource_id': 'resource-2'})

    def test_group_by_with_query_filter(self):
        data = self.get_json(self.PATH,
                             q=[{'field': 'project_id',
                                 'op': 'eq',
                                 'value': 'project-1'}],
                             groupby=['resource_id'])
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(set(['resource_id']), groupby_keys_set)
        self.assertEqual(set(['resource-1', 'resource-2', 'resource-3']),
                         groupby_vals_set)

        for r in data:
            grp = r['groupby']
            if grp == {'resource_id': 'resource-1'}:
                self.assertEqual(2, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(2, r['min'])
                self.assertEqual(2, r['max'])
                self.assertEqual(4, r['sum'])
                self.assertEqual(2, r['avg'])
            elif grp == {'resource_id': 'resource-2'}:
                self.assertEqual(2, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(1, r['min'])
                self.assertEqual(1, r['max'])
                self.assertEqual(2, r['sum'])
                self.assertEqual(1, r['avg'])
            elif grp == {'resource_id': 'resource-3'}:
                self.assertEqual(1, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(4, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(4, r['sum'])
                self.assertEqual(4, r['avg'])

    def test_group_by_with_query_filter_multiple(self):
        data = self.get_json(self.PATH,
                             q=[{'field': 'user_id',
                                 'op': 'eq',
                                 'value': 'user-2'},
                                {'field': 'source',
                                 'op': 'eq',
                                 'value': 'source-1'}],
                             groupby=['project_id', 'resource_id'])
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(set(['project_id', 'resource_id']), groupby_keys_set)
        self.assertEqual(set(['project-1', 'project-2',
                              'resource-1', 'resource-2']),
                         groupby_vals_set)

        for r in data:
            grp = r['groupby']
            if grp == {'project_id': 'project-1',
                       'resource_id': 'resource-1'}:
                self.assertEqual(1, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(2, r['min'])
                self.assertEqual(2, r['max'])
                self.assertEqual(2, r['sum'])
                self.assertEqual(2, r['avg'])
            elif grp == {'project_id': 'project-1',
                         'resource_id': 'resource-2'}:
                self.assertEqual(2, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(1, r['min'])
                self.assertEqual(1, r['max'])
                self.assertEqual(2, r['sum'])
                self.assertEqual(1, r['avg'])
            elif grp == {'project_id': 'project-2',
                         'resource_id': 'resource-2'}:
                self.assertEqual(1, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(4, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(4, r['sum'])
                self.assertEqual(4, r['avg'])
            else:
                self.assertNotEqual(grp, {'project_id': 'project-2',
                                          'resource_id': 'resource-1'})

    def test_group_by_with_period(self):
        data = self.get_json(self.PATH,
                             groupby=['project_id'],
                             period=7200)
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(set(['project_id']), groupby_keys_set)
        self.assertEqual(set(['project-1', 'project-2']), groupby_vals_set)
        period_start_set = set(sub_dict['period_start'] for sub_dict in data)
        period_start_valid = set([u'2013-08-01T10:11:00',
                                  u'2013-08-01T14:11:00',
                                  u'2013-08-01T16:11:00'])
        self.assertEqual(period_start_valid, period_start_set)

        for r in data:
            grp = r['groupby']
            period_start = r['period_start']
            if (grp == {'project_id': 'project-1'} and
                    period_start == u'2013-08-01T10:11:00'):
                self.assertEqual(3, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(1, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(6, r['sum'])
                self.assertEqual(2, r['avg'])
                self.assertEqual(4260, r['duration'])
                self.assertEqual(u'2013-08-01T10:11:00', r['duration_start'])
                self.assertEqual(u'2013-08-01T11:22:00', r['duration_end'])
                self.assertEqual(7200, r['period'])
                self.assertEqual(u'2013-08-01T12:11:00', r['period_end'])
            elif (grp == {'project_id': 'project-1'} and
                    period_start == u'2013-08-01T14:11:00'):
                self.assertEqual(2, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(2, r['min'])
                self.assertEqual(2, r['max'])
                self.assertEqual(4, r['sum'])
                self.assertEqual(2, r['avg'])
                self.assertEqual(4260, r['duration'])
                self.assertEqual(u'2013-08-01T14:59:00', r['duration_start'])
                self.assertEqual(u'2013-08-01T16:10:00', r['duration_end'])
                self.assertEqual(7200, r['period'])
                self.assertEqual(u'2013-08-01T16:11:00', r['period_end'])
            elif (grp == {'project_id': 'project-2'} and
                    period_start == u'2013-08-01T14:11:00'):
                self.assertEqual(1, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(2, r['min'])
                self.assertEqual(2, r['max'])
                self.assertEqual(2, r['sum'])
                self.assertEqual(2, r['avg'])
                self.assertEqual(0, r['duration'])
                self.assertEqual(u'2013-08-01T15:37:00', r['duration_start'])
                self.assertEqual(u'2013-08-01T15:37:00', r['duration_end'])
                self.assertEqual(7200, r['period'])
                self.assertEqual(u'2013-08-01T16:11:00', r['period_end'])
            elif (grp == {'project_id': 'project-2'} and
                    period_start == u'2013-08-01T16:11:00'):
                self.assertEqual(1, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(4, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(4, r['sum'])
                self.assertEqual(4, r['avg'])
                self.assertEqual(0, r['duration'])
                self.assertEqual(u'2013-08-01T17:28:00', r['duration_start'])
                self.assertEqual(u'2013-08-01T17:28:00', r['duration_end'])
                self.assertEqual(7200, r['period'])
                self.assertEqual(u'2013-08-01T18:11:00', r['period_end'])
            else:
                self.assertNotEqual([grp, period_start],
                                    [{'project_id': 'project-1'},
                                     u'2013-08-01T16:11:00'])
                self.assertNotEqual([grp, period_start],
                                    [{'project_id': 'project-2'},
                                     u'2013-08-01T10:11:00'])

    def test_group_by_with_query_filter_and_period(self):
        data = self.get_json(self.PATH,
                             q=[{'field': 'source',
                                 'op': 'eq',
                                 'value': 'source-1'}],
                             groupby=['project_id'],
                             period=7200)
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(set(['project_id']), groupby_keys_set)
        self.assertEqual(set(['project-1', 'project-2']), groupby_vals_set)
        period_start_set = set(sub_dict['period_start'] for sub_dict in data)
        period_start_valid = set([u'2013-08-01T10:11:00',
                                  u'2013-08-01T14:11:00',
                                  u'2013-08-01T16:11:00'])
        self.assertEqual(period_start_valid, period_start_set)

        for r in data:
            grp = r['groupby']
            period_start = r['period_start']
            if (grp == {'project_id': 'project-1'} and
                    period_start == u'2013-08-01T10:11:00'):
                self.assertEqual(2, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(1, r['min'])
                self.assertEqual(1, r['max'])
                self.assertEqual(2, r['sum'])
                self.assertEqual(1, r['avg'])
                self.assertEqual(1740, r['duration'])
                self.assertEqual(u'2013-08-01T10:11:00', r['duration_start'])
                self.assertEqual(u'2013-08-01T10:40:00', r['duration_end'])
                self.assertEqual(7200, r['period'])
                self.assertEqual(u'2013-08-01T12:11:00', r['period_end'])
            elif (grp == {'project_id': 'project-1'} and
                    period_start == u'2013-08-01T14:11:00'):
                self.assertEqual(1, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(2, r['min'])
                self.assertEqual(2, r['max'])
                self.assertEqual(2, r['sum'])
                self.assertEqual(2, r['avg'])
                self.assertEqual(0, r['duration'])
                self.assertEqual(u'2013-08-01T14:59:00', r['duration_start'])
                self.assertEqual(u'2013-08-01T14:59:00', r['duration_end'])
                self.assertEqual(7200, r['period'])
                self.assertEqual(u'2013-08-01T16:11:00', r['period_end'])
            elif (grp == {'project_id': 'project-2'} and
                    period_start == u'2013-08-01T16:11:00'):
                self.assertEqual(1, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(4, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(4, r['sum'])
                self.assertEqual(4, r['avg'])
                self.assertEqual(0, r['duration'])
                self.assertEqual(u'2013-08-01T17:28:00', r['duration_start'])
                self.assertEqual(u'2013-08-01T17:28:00', r['duration_end'])
                self.assertEqual(7200, r['period'])
                self.assertEqual(u'2013-08-01T18:11:00', r['period_end'])
            else:
                self.assertNotEqual([grp, period_start],
                                    [{'project_id': 'project-1'},
                                     u'2013-08-01T16:11:00'])
                self.assertNotEqual([grp, period_start],
                                    [{'project_id': 'project-2'},
                                     u'2013-08-01T10:11:00'])
                self.assertNotEqual([grp, period_start],
                                    [{'project_id': 'project-2'},
                                     u'2013-08-01T14:11:00'])

    def test_group_by_start_timestamp_after(self):
        data = self.get_json(self.PATH,
                             q=[{'field': 'timestamp',
                                 'op': 'ge',
                                 'value': '2013-08-01T17:28:01'}],
                             groupby=['project_id'])
        self.assertEqual([], data)

    def test_group_by_end_timestamp_before(self):
        data = self.get_json(self.PATH,
                             q=[{'field': 'timestamp',
                                 'op': 'le',
                                 'value': '2013-08-01T10:10:59'}],
                             groupby=['project_id'])
        self.assertEqual([], data)

    def test_group_by_start_timestamp(self):
        data = self.get_json(self.PATH,
                             q=[{'field': 'timestamp',
                                 'op': 'ge',
                                 'value': '2013-08-01T14:58:00'}],
                             groupby=['project_id'])
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(set(['project_id']), groupby_keys_set)
        self.assertEqual(set(['project-1', 'project-2']), groupby_vals_set)

        for r in data:
            grp = r['groupby']
            if grp == {'project_id': 'project-1'}:
                self.assertEqual(2, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(2, r['min'])
                self.assertEqual(2, r['max'])
                self.assertEqual(4, r['sum'])
                self.assertEqual(2, r['avg'])
            elif grp == {'project_id': 'project-2'}:
                self.assertEqual(2, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(2, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(6, r['sum'])
                self.assertEqual(3, r['avg'])

    def test_group_by_end_timestamp(self):
        data = self.get_json(self.PATH,
                             q=[{'field': 'timestamp',
                                 'op': 'le',
                                 'value': '2013-08-01T11:45:00'}],
                             groupby=['project_id'])
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(set(['project_id']), groupby_keys_set)
        self.assertEqual(set(['project-1']), groupby_vals_set)

        for r in data:
            grp = r['groupby']
            if grp == {'project_id': 'project-1'}:
                self.assertEqual(3, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(1, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(6, r['sum'])
                self.assertEqual(2, r['avg'])

    def test_group_by_start_end_timestamp(self):
        data = self.get_json(self.PATH,
                             q=[{'field': 'timestamp',
                                 'op': 'ge',
                                 'value': '2013-08-01T08:17:03'},
                                {'field': 'timestamp',
                                 'op': 'le',
                                 'value': '2013-08-01T23:59:59'}],
                             groupby=['project_id'])
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(set(['project_id']), groupby_keys_set)
        self.assertEqual(set(['project-1', 'project-2']), groupby_vals_set)

        for r in data:
            grp = r['groupby']
            if grp == {'project_id': 'project-1'}:
                self.assertEqual(5, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(1, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(10, r['sum'])
                self.assertEqual(2, r['avg'])
            elif grp == {'project_id': 'project-2'}:
                self.assertEqual(2, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(2, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(6, r['sum'])
                self.assertEqual(3, r['avg'])

    def test_group_by_start_end_timestamp_with_query_filter(self):
        data = self.get_json(self.PATH,
                             q=[{'field': 'project_id',
                                 'op': 'eq',
                                 'value': 'project-1'},
                                {'field': 'timestamp',
                                 'op': 'ge',
                                 'value': '2013-08-01T11:01:00'},
                                {'field': 'timestamp',
                                 'op': 'le',
                                 'value': '2013-08-01T20:00:00'}],
                             groupby=['resource_id'])
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(set(['resource_id']), groupby_keys_set)
        self.assertEqual(set(['resource-1', 'resource-3']), groupby_vals_set)

        for r in data:
            grp = r['groupby']
            if grp == {'resource_id': 'resource-1'}:
                self.assertEqual(2, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(2, r['min'])
                self.assertEqual(2, r['max'])
                self.assertEqual(4, r['sum'])
                self.assertEqual(2, r['avg'])
            elif grp == {'resource_id': 'resource-3'}:
                self.assertEqual(1, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(4, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(4, r['sum'])
                self.assertEqual(4, r['avg'])

    def test_group_by_start_end_timestamp_with_period(self):
        data = self.get_json(self.PATH,
                             q=[{'field': 'timestamp',
                                 'op': 'ge',
                                 'value': '2013-08-01T14:00:00'},
                                {'field': 'timestamp',
                                 'op': 'le',
                                 'value': '2013-08-01T17:00:00'}],
                             groupby=['project_id'],
                             period=3600)
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(set(['project_id']), groupby_keys_set)
        self.assertEqual(set(['project-1', 'project-2']), groupby_vals_set)
        period_start_set = set(sub_dict['period_start'] for sub_dict in data)
        period_start_valid = set([u'2013-08-01T14:00:00',
                                  u'2013-08-01T15:00:00',
                                  u'2013-08-01T16:00:00'])
        self.assertEqual(period_start_valid, period_start_set)

        for r in data:
            grp = r['groupby']
            period_start = r['period_start']
            if (grp == {'project_id': 'project-1'} and
                    period_start == u'2013-08-01T14:00:00'):
                self.assertEqual(1, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(2, r['min'])
                self.assertEqual(2, r['max'])
                self.assertEqual(2, r['sum'])
                self.assertEqual(2, r['avg'])
                self.assertEqual(0, r['duration'])
                self.assertEqual(u'2013-08-01T14:59:00', r['duration_start'])
                self.assertEqual(u'2013-08-01T14:59:00', r['duration_end'])
                self.assertEqual(3600, r['period'])
                self.assertEqual(u'2013-08-01T15:00:00', r['period_end'])
            elif (grp == {'project_id': 'project-1'} and
                    period_start == u'2013-08-01T16:00:00'):
                self.assertEqual(1, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(2, r['min'])
                self.assertEqual(2, r['max'])
                self.assertEqual(2, r['sum'])
                self.assertEqual(2, r['avg'])
                self.assertEqual(0, r['duration'])
                self.assertEqual(u'2013-08-01T16:10:00', r['duration_start'])
                self.assertEqual(u'2013-08-01T16:10:00', r['duration_end'])
                self.assertEqual(3600, r['period'])
                self.assertEqual(u'2013-08-01T17:00:00', r['period_end'])
            elif (grp == {'project_id': 'project-2'} and
                    period_start == u'2013-08-01T15:00:00'):
                self.assertEqual(1, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(2, r['min'])
                self.assertEqual(2, r['max'])
                self.assertEqual(2, r['sum'])
                self.assertEqual(2, r['avg'])
                self.assertEqual(0, r['duration'])
                self.assertEqual(u'2013-08-01T15:37:00', r['duration_start'])
                self.assertEqual(u'2013-08-01T15:37:00', r['duration_end'])
                self.assertEqual(3600, r['period'])
                self.assertEqual(u'2013-08-01T16:00:00', r['period_end'])
            else:
                self.assertNotEqual([grp, period_start],
                                    [{'project_id': 'project-1'},
                                     u'2013-08-01T15:00:00'])
                self.assertNotEqual([grp, period_start],
                                    [{'project_id': 'project-2'},
                                     u'2013-08-01T14:00:00'])
                self.assertNotEqual([grp, period_start],
                                    [{'project_id': 'project-2'},
                                     u'2013-08-01T16:00:00'])

    def test_group_by_start_end_timestamp_with_query_filter_and_period(self):
        data = self.get_json(self.PATH,
                             q=[{'field': 'source',
                                 'op': 'eq',
                                 'value': 'source-1'},
                                {'field': 'timestamp',
                                 'op': 'ge',
                                 'value': '2013-08-01T10:00:00'},
                                {'field': 'timestamp',
                                 'op': 'le',
                                 'value': '2013-08-01T18:00:00'}],
                             groupby=['project_id'],
                             period=7200)
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(set(['project_id']), groupby_keys_set)
        self.assertEqual(set(['project-1', 'project-2']), groupby_vals_set)
        period_start_set = set(sub_dict['period_start'] for sub_dict in data)
        period_start_valid = set([u'2013-08-01T10:00:00',
                                  u'2013-08-01T14:00:00',
                                  u'2013-08-01T16:00:00'])
        self.assertEqual(period_start_valid, period_start_set)

        for r in data:
            grp = r['groupby']
            period_start = r['period_start']
            if (grp == {'project_id': 'project-1'} and
                    period_start == u'2013-08-01T10:00:00'):
                self.assertEqual(2, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(1, r['min'])
                self.assertEqual(1, r['max'])
                self.assertEqual(2, r['sum'])
                self.assertEqual(1, r['avg'])
                self.assertEqual(1740, r['duration'])
                self.assertEqual(u'2013-08-01T10:11:00', r['duration_start'])
                self.assertEqual(u'2013-08-01T10:40:00', r['duration_end'])
                self.assertEqual(7200, r['period'])
                self.assertEqual(u'2013-08-01T12:00:00', r['period_end'])
            elif (grp == {'project_id': 'project-1'} and
                    period_start == u'2013-08-01T14:00:00'):
                self.assertEqual(1, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(2, r['min'])
                self.assertEqual(2, r['max'])
                self.assertEqual(2, r['sum'])
                self.assertEqual(2, r['avg'])
                self.assertEqual(0, r['duration'])
                self.assertEqual(u'2013-08-01T14:59:00', r['duration_start'])
                self.assertEqual(u'2013-08-01T14:59:00', r['duration_end'])
                self.assertEqual(7200, r['period'])
                self.assertEqual(u'2013-08-01T16:00:00', r['period_end'])
            elif (grp == {'project_id': 'project-2'} and
                    period_start == u'2013-08-01T16:00:00'):
                self.assertEqual(1, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(4, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(4, r['sum'])
                self.assertEqual(4, r['avg'])
                self.assertEqual(0, r['duration'])
                self.assertEqual(u'2013-08-01T17:28:00', r['duration_start'])
                self.assertEqual(u'2013-08-01T17:28:00', r['duration_end'])
                self.assertEqual(7200, r['period'])
                self.assertEqual(u'2013-08-01T18:00:00', r['period_end'])
            else:
                self.assertNotEqual([grp, period_start],
                                    [{'project_id': 'project-1'},
                                     u'2013-08-01T16:00:00'])
                self.assertNotEqual([grp, period_start],
                                    [{'project_id': 'project-2'},
                                     u'2013-08-01T10:00:00'])
                self.assertNotEqual([grp, period_start],
                                    [{'project_id': 'project-2'},
                                     u'2013-08-01T14:00:00'])


@tests_db.run_with('mongodb', 'hbase')
class TestGroupBySource(v2.FunctionalTest):

    # FIXME(terriyu): We have to put test_group_by_source in its own class
    # because SQLAlchemy currently doesn't support group by source statistics.
    # When group by source is supported in SQLAlchemy, this test should be
    # moved to TestGroupByInstance with all the other group by statistics
    # tests.

    PATH = '/meters/instance/statistics'

    def setUp(self):
        super(TestGroupBySource, self).setUp()

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
            msg = utils.meter_message_from_counter(
                c, self.CONF.publisher.telemetry_secret,
            )
            self.conn.record_metering_data(msg)

    def tearDown(self):
        self.conn.clear()
        super(TestGroupBySource, self).tearDown()

    def test_group_by_source(self):
        data = self.get_json(self.PATH, groupby=['source'])
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(set(['source']), groupby_keys_set)
        self.assertEqual(set(['source-1', 'source-2', 'source-3']),
                         groupby_vals_set)

        for r in data:
            grp = r['groupby']
            if grp == {'source': 'source-1'}:
                self.assertEqual(4, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(1, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(8, r['sum'])
                self.assertEqual(2, r['avg'])
            elif grp == {'source': 'source-2'}:
                self.assertEqual(2, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(2, r['min'])
                self.assertEqual(2, r['max'])
                self.assertEqual(4, r['sum'])
                self.assertEqual(2, r['avg'])
            elif grp == {'source': 'source-3'}:
                self.assertEqual(1, r['count'])
                self.assertEqual('s', r['unit'])
                self.assertEqual(4, r['min'])
                self.assertEqual(4, r['max'])
                self.assertEqual(4, r['sum'])
                self.assertEqual(4, r['avg'])


class TestSelectableAggregates(v2.FunctionalTest):

    PATH = '/meters/instance/statistics'

    def setUp(self):
        super(TestSelectableAggregates, self).setUp()

        test_sample_data = (
            {'volume': 2, 'user': 'user-1', 'project': 'project-1',
             'resource': 'resource-1', 'timestamp': (2013, 8, 1, 16, 10),
             'metadata_flavor': 'm1.tiny', 'metadata_event': 'event-1',
             'source': 'source'},
            {'volume': 2, 'user': 'user-2', 'project': 'project-2',
             'resource': 'resource-3', 'timestamp': (2013, 8, 1, 15, 37),
             'metadata_flavor': 'm1.large', 'metadata_event': 'event-1',
             'source': 'source'},
            {'volume': 1, 'user': 'user-2', 'project': 'project-2',
             'resource': 'resource-5', 'timestamp': (2013, 8, 1, 10, 11),
             'metadata_flavor': 'm1.medium', 'metadata_event': 'event-2',
             'source': 'source'},
            {'volume': 2, 'user': 'user-1', 'project': 'project-1',
             'resource': 'resource-2', 'timestamp': (2013, 8, 1, 10, 40),
             'metadata_flavor': 'm1.large', 'metadata_event': 'event-2',
             'source': 'source'},
            {'volume': 2, 'user': 'user-2', 'project': 'project-2',
             'resource': 'resource-4', 'timestamp': (2013, 8, 1, 14, 59),
             'metadata_flavor': 'm1.large', 'metadata_event': 'event-2',
             'source': 'source'},
            {'volume': 5, 'user': 'user-1', 'project': 'project-1',
             'resource': 'resource-2', 'timestamp': (2013, 8, 1, 17, 28),
             'metadata_flavor': 'm1.large', 'metadata_event': 'event-2',
             'source': 'source'},
            {'volume': 4, 'user': 'user-2', 'project': 'project-2',
             'resource': 'resource-3', 'timestamp': (2013, 8, 1, 11, 22),
             'metadata_flavor': 'm1.large', 'metadata_event': 'event-2',
             'source': 'source'},
            {'volume': 9, 'user': 'user-3', 'project': 'project-3',
             'resource': 'resource-4', 'timestamp': (2013, 8, 1, 11, 59),
             'metadata_flavor': 'm1.large', 'metadata_event': 'event-3',
             'source': 'source'},
        )

        for test_sample in test_sample_data:
            c = sample.Sample(
                'instance',
                sample.TYPE_GAUGE,
                unit='instance',
                volume=test_sample['volume'],
                user_id=test_sample['user'],
                project_id=test_sample['project'],
                resource_id=test_sample['resource'],
                timestamp=datetime.datetime(*test_sample['timestamp']),
                resource_metadata={'flavor': test_sample['metadata_flavor'],
                                   'event': test_sample['metadata_event'], },
                source=test_sample['source'],
            )
            msg = utils.meter_message_from_counter(
                c, self.CONF.publisher.telemetry_secret,
            )
            self.conn.record_metering_data(msg)

    def _do_test_per_tenant_selectable_standard_aggregate(self,
                                                          aggregate,
                                                          expected_values):
        agg_args = {'aggregate.func': aggregate}
        data = self.get_json(self.PATH, groupby=['project_id'], **agg_args)
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(set(['project_id']), groupby_keys_set)
        projects = ['project-1', 'project-2', 'project-3']
        self.assertEqual(set(projects), groupby_vals_set)

        standard_aggregates = set(['count', 'min', 'max', 'sum', 'avg'])
        for r in data:
            grp = r['groupby']
            for project in projects:
                if grp == {'project_id': project}:
                    expected = expected_values[projects.index(project)]
                    self.assertEqual('instance', r['unit'])
                    self.assertAlmostEqual(r[aggregate], expected)
                    self.assertIn('aggregate', r)
                    self.assertIn(aggregate, r['aggregate'])
                    self.assertAlmostEqual(r['aggregate'][aggregate], expected)
                    for a in standard_aggregates - set([aggregate]):
                        self.assertNotIn(a, r)

    def test_per_tenant_selectable_max(self):
        self._do_test_per_tenant_selectable_standard_aggregate('max',
                                                               [5, 4, 9])

    def test_per_tenant_selectable_min(self):
        self._do_test_per_tenant_selectable_standard_aggregate('min',
                                                               [2, 1, 9])

    def test_per_tenant_selectable_sum(self):
        self._do_test_per_tenant_selectable_standard_aggregate('sum',
                                                               [9, 9, 9])

    def test_per_tenant_selectable_avg(self):
        self._do_test_per_tenant_selectable_standard_aggregate('avg',
                                                               [3, 2.25, 9])

    def test_per_tenant_selectable_count(self):
        self._do_test_per_tenant_selectable_standard_aggregate('count',
                                                               [3, 4, 1])

    def test_per_tenant_selectable_parameterized_aggregate(self):
        agg_args = {'aggregate.func': 'cardinality',
                    'aggregate.param': 'resource_id'}
        data = self.get_json(self.PATH, groupby=['project_id'], **agg_args)
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(set(['project_id']), groupby_keys_set)
        projects = ['project-1', 'project-2', 'project-3']
        self.assertEqual(set(projects), groupby_vals_set)

        aggregate = 'cardinality/resource_id'
        expected_values = [2.0, 3.0, 1.0]
        standard_aggregates = set(['count', 'min', 'max', 'sum', 'avg'])
        for r in data:
            grp = r['groupby']
            for project in projects:
                if grp == {'project_id': project}:
                    expected = expected_values[projects.index(project)]
                    self.assertEqual('instance', r['unit'])
                    self.assertNotIn(aggregate, r)
                    self.assertIn('aggregate', r)
                    self.assertIn(aggregate, r['aggregate'])
                    self.assertEqual(expected, r['aggregate'][aggregate])
                    for a in standard_aggregates:
                        self.assertNotIn(a, r)

    def test_large_quantum_selectable_parameterized_aggregate(self):
        # add a large number of datapoints that won't impact on cardinality
        # if the computation logic is tolerant of different DB behavior on
        # larger numbers of samples per-period
        for i in range(200):
            s = sample.Sample(
                'instance',
                sample.TYPE_GAUGE,
                unit='instance',
                volume=i * 1.0,
                user_id='user-1',
                project_id='project-1',
                resource_id='resource-1',
                timestamp=datetime.datetime(2013, 8, 1, 11, i % 60),
                resource_metadata={'flavor': 'm1.tiny',
                                   'event': 'event-1', },
                source='source',
            )
            msg = utils.meter_message_from_counter(
                s, self.CONF.publisher.telemetry_secret,
            )
            self.conn.record_metering_data(msg)

        agg_args = {'aggregate.func': 'cardinality',
                    'aggregate.param': 'resource_id'}
        data = self.get_json(self.PATH, **agg_args)

        aggregate = 'cardinality/resource_id'
        expected_value = 5.0
        standard_aggregates = set(['count', 'min', 'max', 'sum', 'avg'])
        r = data[0]
        self.assertNotIn(aggregate, r)
        self.assertIn('aggregate', r)
        self.assertIn(aggregate, r['aggregate'])
        self.assertEqual(expected_value, r['aggregate'][aggregate])
        for a in standard_aggregates:
            self.assertNotIn(a, r)

    def test_repeated_unparameterized_aggregate(self):
        agg_params = 'aggregate.func=count&aggregate.func=count'
        data = self.get_json(self.PATH, override_params=agg_params)

        aggregate = 'count'
        expected_value = 8.0
        standard_aggregates = set(['min', 'max', 'sum', 'avg'])
        r = data[0]
        self.assertIn(aggregate, r)
        self.assertEqual(expected_value, r[aggregate])
        self.assertIn('aggregate', r)
        self.assertIn(aggregate, r['aggregate'])
        self.assertEqual(expected_value, r['aggregate'][aggregate])
        for a in standard_aggregates:
            self.assertNotIn(a, r)

    def test_fully_repeated_parameterized_aggregate(self):
        agg_params = ('aggregate.func=cardinality&'
                      'aggregate.param=resource_id&'
                      'aggregate.func=cardinality&'
                      'aggregate.param=resource_id&')
        data = self.get_json(self.PATH, override_params=agg_params)

        aggregate = 'cardinality/resource_id'
        expected_value = 5.0
        standard_aggregates = set(['count', 'min', 'max', 'sum', 'avg'])
        r = data[0]
        self.assertIn('aggregate', r)
        self.assertNotIn(aggregate, r)
        self.assertIn(aggregate, r['aggregate'])
        self.assertEqual(expected_value, r['aggregate'][aggregate])
        for a in standard_aggregates:
            self.assertNotIn(a, r)

    def test_partially_repeated_parameterized_aggregate(self):
        agg_params = ('aggregate.func=cardinality&'
                      'aggregate.param=resource_id&'
                      'aggregate.func=cardinality&'
                      'aggregate.param=project_id&')
        data = self.get_json(self.PATH, override_params=agg_params)

        expected_values = {'cardinality/resource_id': 5.0,
                           'cardinality/project_id': 3.0}
        standard_aggregates = set(['count', 'min', 'max', 'sum', 'avg'])
        r = data[0]
        self.assertIn('aggregate', r)
        for aggregate in expected_values.keys():
            self.assertNotIn(aggregate, r)
            self.assertIn(aggregate, r['aggregate'])
            self.assertEqual(expected_values[aggregate],
                             r['aggregate'][aggregate])
        for a in standard_aggregates:
            self.assertNotIn(a, r)

    def test_bad_selectable_parameterized_aggregate(self):
        agg_args = {'aggregate.func': 'cardinality',
                    'aggregate.param': 'injection_attack'}
        resp = self.get_json(self.PATH, status=[400],
                             groupby=['project_id'], **agg_args)
        self.assertIn('error_message', resp)
        self.assertEqual(resp['error_message'].get('faultcode'),
                         'Client')
        self.assertEqual(resp['error_message'].get('faultstring'),
                         'Bad aggregate: cardinality.injection_attack')


@tests_db.run_with('mongodb', 'hbase')
class TestUnparameterizedAggregates(v2.FunctionalTest):

    # We put the stddev test case in a separate class so that we
    # can easily exclude the sqlalchemy scenario, as sqlite doesn't
    # support the stddev_pop function and fails ungracefully with
    # OperationalError when it is used. However we still want to
    # test the corresponding functionality in the mongo driver.
    # For hbase, the skip on NotImplementedError logic works
    # in the usual way.

    PATH = '/meters/instance/statistics'

    def setUp(self):
        super(TestUnparameterizedAggregates, self).setUp()

        test_sample_data = (
            {'volume': 2, 'user': 'user-1', 'project': 'project-1',
             'resource': 'resource-1', 'timestamp': (2013, 8, 1, 16, 10),
             'metadata_flavor': 'm1.tiny', 'metadata_event': 'event-1',
             'source': 'source'},
            {'volume': 2, 'user': 'user-2', 'project': 'project-2',
             'resource': 'resource-3', 'timestamp': (2013, 8, 1, 15, 37),
             'metadata_flavor': 'm1.large', 'metadata_event': 'event-1',
             'source': 'source'},
            {'volume': 1, 'user': 'user-2', 'project': 'project-2',
             'resource': 'resource-5', 'timestamp': (2013, 8, 1, 10, 11),
             'metadata_flavor': 'm1.medium', 'metadata_event': 'event-2',
             'source': 'source'},
            {'volume': 2, 'user': 'user-1', 'project': 'project-1',
             'resource': 'resource-2', 'timestamp': (2013, 8, 1, 10, 40),
             'metadata_flavor': 'm1.large', 'metadata_event': 'event-2',
             'source': 'source'},
            {'volume': 2, 'user': 'user-2', 'project': 'project-2',
             'resource': 'resource-4', 'timestamp': (2013, 8, 1, 14, 59),
             'metadata_flavor': 'm1.large', 'metadata_event': 'event-2',
             'source': 'source'},
            {'volume': 5, 'user': 'user-1', 'project': 'project-1',
             'resource': 'resource-2', 'timestamp': (2013, 8, 1, 17, 28),
             'metadata_flavor': 'm1.large', 'metadata_event': 'event-2',
             'source': 'source'},
            {'volume': 4, 'user': 'user-2', 'project': 'project-2',
             'resource': 'resource-3', 'timestamp': (2013, 8, 1, 11, 22),
             'metadata_flavor': 'm1.large', 'metadata_event': 'event-2',
             'source': 'source'},
            {'volume': 9, 'user': 'user-3', 'project': 'project-3',
             'resource': 'resource-4', 'timestamp': (2013, 8, 1, 11, 59),
             'metadata_flavor': 'm1.large', 'metadata_event': 'event-3',
             'source': 'source'},
        )

        for test_sample in test_sample_data:
            c = sample.Sample(
                'instance',
                sample.TYPE_GAUGE,
                unit='instance',
                volume=test_sample['volume'],
                user_id=test_sample['user'],
                project_id=test_sample['project'],
                resource_id=test_sample['resource'],
                timestamp=datetime.datetime(*test_sample['timestamp']),
                resource_metadata={'flavor': test_sample['metadata_flavor'],
                                   'event': test_sample['metadata_event'], },
                source=test_sample['source'],
            )
            msg = utils.meter_message_from_counter(
                c, self.CONF.publisher.telemetry_secret,
            )
            self.conn.record_metering_data(msg)

    def test_per_tenant_selectable_unparameterized_aggregate(self):
        agg_args = {'aggregate.func': 'stddev'}
        data = self.get_json(self.PATH, groupby=['project_id'], **agg_args)
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(set(['project_id']), groupby_keys_set)
        projects = ['project-1', 'project-2', 'project-3']
        self.assertEqual(set(projects), groupby_vals_set)

        aggregate = 'stddev'
        expected_values = [1.4142, 1.0897, 0.0]
        standard_aggregates = set(['count', 'min', 'max', 'sum', 'avg'])
        for r in data:
            grp = r['groupby']
            for project in projects:
                if grp == {'project_id': project}:
                    expected = expected_values[projects.index(project)]
                    self.assertEqual('instance', r['unit'])
                    self.assertNotIn(aggregate, r)
                    self.assertIn('aggregate', r)
                    self.assertIn(aggregate, r['aggregate'])
                    self.assertAlmostEqual(r['aggregate'][aggregate],
                                           expected,
                                           places=4)
                    for a in standard_aggregates:
                        self.assertNotIn(a, r)


@tests_db.run_with('mongodb')
class TestBigValueStatistics(v2.FunctionalTest):

    PATH = '/meters/volume.size/statistics'

    def setUp(self):
        super(TestBigValueStatistics, self).setUp()
        for i in range(0, 3):
            s = sample.Sample(
                'volume.size',
                'gauge',
                'GiB',
                (i + 1) * (10 ** 12),
                'user-id',
                'project1',
                'resource-id',
                timestamp=datetime.datetime(2012, 9, 25, 10 + i, 30 + i),
                resource_metadata={'display_name': 'test-volume',
                                   'tag': 'self.sample',
                                   },
                source='source1',
            )
            msg = utils.meter_message_from_counter(
                s, self.CONF.publisher.telemetry_secret,
            )
            self.conn.record_metering_data(msg)

    def test_big_value_statistics(self):
        data = self.get_json(self.PATH)

        expected_values = {'count': 3,
                           'min': 10 ** 12,
                           'max': 3 * 10 ** 12,
                           'sum': 6 * 10 ** 12,
                           'avg': 2 * 10 ** 12}
        self.assertEqual(1, len(data))
        for d in data:
            for name, expected_value in expected_values.items():
                self.assertIn(name, d)
                self.assertEqual(expected_value, d[name])
