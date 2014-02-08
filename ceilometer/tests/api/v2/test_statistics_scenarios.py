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
"""Test events statistics retrieval."""

import datetime

import testscenarios

from ceilometer.publisher import utils
from ceilometer import sample
from ceilometer.tests.api.v2 import FunctionalTest
from ceilometer.tests import db as tests_db

load_tests = testscenarios.load_tests_apply_scenarios


class TestMaxProjectVolume(FunctionalTest,
                           tests_db.MixinTestsWithBackendScenarios):

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
                s,
                self.CONF.publisher.metering_secret,
            )
            self.conn.record_metering_data(msg)

    def test_no_time_bounds(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            }])
        self.assertEqual(data[0]['max'], 7)
        self.assertEqual(data[0]['count'], 3)

    def test_start_timestamp(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'ge',
                                            'value': '2012-09-25T11:30:00',
                                            },
                                           ])
        self.assertEqual(data[0]['max'], 7)
        self.assertEqual(data[0]['count'], 2)

    def test_start_timestamp_after(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'ge',
                                            'value': '2012-09-25T12:34:00',
                                            },
                                           ])
        self.assertEqual(data, [])

    def test_end_timestamp(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'le',
                                            'value': '2012-09-25T11:30:00',
                                            },
                                           ])
        self.assertEqual(data[0]['max'], 5)
        self.assertEqual(data[0]['count'], 1)

    def test_end_timestamp_before(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'le',
                                            'value': '2012-09-25T09:54:00',
                                            },
                                           ])
        self.assertEqual(data, [])

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
        self.assertEqual(data[0]['max'], 6)
        self.assertEqual(data[0]['count'], 1)


class TestMaxResourceVolume(FunctionalTest,
                            tests_db.MixinTestsWithBackendScenarios):

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
                s,
                self.CONF.publisher.metering_secret,
            )
            self.conn.record_metering_data(msg)

    def test_no_time_bounds(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            }])
        self.assertEqual(data[0]['max'], 7)
        self.assertEqual(data[0]['count'], 3)

    def test_no_time_bounds_with_period(self):
        data = self.get_json(self.PATH,
                             q=[{'field': 'resource_id',
                                 'value': 'resource-id'}],
                             period=3600)
        self.assertEqual(len(data), 3)
        self.assertEqual(set(x['duration_start'] for x in data),
                         set([u'2012-09-25T10:30:00',
                              u'2012-09-25T12:32:00',
                              u'2012-09-25T11:31:00']))
        self.assertEqual(data[0]['period'], 3600)
        self.assertEqual(set(x['period_start'] for x in data),
                         set([u'2012-09-25T10:30:00',
                              u'2012-09-25T11:30:00',
                              u'2012-09-25T12:30:00']))

    def test_period_with_negative_value(self):
        resp = self.get_json(self.PATH, expect_errors=True,
                             q=[{'field': 'resource_id',
                                 'value': 'resource-id'}],
                             period=-1)
        self.assertEqual(400, resp.status_code)

    def test_start_timestamp(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'ge',
                                            'value': '2012-09-25T11:30:00',
                                            },
                                           ])
        self.assertEqual(data[0]['max'], 7)
        self.assertEqual(data[0]['count'], 2)

    def test_start_timestamp_after(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'ge',
                                            'value': '2012-09-25T12:34:00',
                                            },
                                           ])
        self.assertEqual(data, [])

    def test_end_timestamp(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'le',
                                            'value': '2012-09-25T11:30:00',
                                            },
                                           ])
        self.assertEqual(data[0]['max'], 5)
        self.assertEqual(data[0]['count'], 1)

    def test_end_timestamp_before(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'le',
                                            'value': '2012-09-25T09:54:00',
                                            },
                                           ])
        self.assertEqual(data, [])

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
        self.assertEqual(data[0]['max'], 6)
        self.assertEqual(data[0]['count'], 1)


class TestSumProjectVolume(FunctionalTest,
                           tests_db.MixinTestsWithBackendScenarios):

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
                s,
                self.CONF.publisher.metering_secret,
            )
            self.conn.record_metering_data(msg)

    def test_no_time_bounds(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            }])
        expected = 5 + 6 + 7
        self.assertEqual(data[0]['sum'], expected)
        self.assertEqual(data[0]['count'], 3)

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
        self.assertEqual(data[0]['sum'], expected)
        self.assertEqual(data[0]['count'], 2)

    def test_start_timestamp_after(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'ge',
                                            'value': '2012-09-25T12:34:00',
                                            },
                                           ])
        self.assertEqual(data, [])

    def test_end_timestamp(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'le',
                                            'value': '2012-09-25T11:30:00',
                                            },
                                           ])
        self.assertEqual(data[0]['sum'], 5)
        self.assertEqual(data[0]['count'], 1)

    def test_end_timestamp_before(self):
        data = self.get_json(self.PATH, q=[{'field': 'project_id',
                                            'value': 'project1',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'le',
                                            'value': '2012-09-25T09:54:00',
                                            },
                                           ])
        self.assertEqual(data, [])

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
        self.assertEqual(data[0]['sum'], 6)
        self.assertEqual(data[0]['count'], 1)


class TestSumResourceVolume(FunctionalTest,
                            tests_db.MixinTestsWithBackendScenarios):

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
                s,
                self.CONF.publisher.metering_secret,
            )
            self.conn.record_metering_data(msg)

    def test_no_time_bounds(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            }])
        self.assertEqual(data[0]['sum'], 5 + 6 + 7)
        self.assertEqual(data[0]['count'], 3)

    def test_no_time_bounds_with_period(self):
        data = self.get_json(self.PATH,
                             q=[{'field': 'resource_id',
                                 'value': 'resource-id'}],
                             period=1800)
        self.assertEqual(len(data), 3)
        self.assertEqual(set(x['duration_start'] for x in data),
                         set([u'2012-09-25T10:30:00',
                              u'2012-09-25T12:32:00',
                              u'2012-09-25T11:31:00']))
        self.assertEqual(data[0]['period'], 1800)
        self.assertEqual(set(x['period_start'] for x in data),
                         set([u'2012-09-25T10:30:00',
                              u'2012-09-25T11:30:00',
                              u'2012-09-25T12:30:00']))

    def test_start_timestamp(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'ge',
                                            'value': '2012-09-25T11:30:00',
                                            }])
        self.assertEqual(data[0]['sum'], 6 + 7)
        self.assertEqual(data[0]['count'], 2)

    def test_start_timestamp_with_period(self):
        data = self.get_json(self.PATH,
                             q=[{'field': 'resource_id',
                                 'value': 'resource-id'},
                                {'field': 'timestamp',
                                 'op': 'ge',
                                 'value': '2012-09-25T10:15:00'}],
                             period=7200)
        self.assertEqual(len(data), 2)
        self.assertEqual(set(x['duration_start'] for x in data),
                         set([u'2012-09-25T10:30:00',
                              u'2012-09-25T12:32:00']))
        self.assertEqual(data[0]['period'], 7200)
        self.assertEqual(set(x['period_start'] for x in data),
                         set([u'2012-09-25T10:15:00',
                              u'2012-09-25T12:15:00']))

    def test_start_timestamp_after(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'ge',
                                            'value': '2012-09-25T12:34:00',
                                            }])
        self.assertEqual(data, [])

    def test_end_timestamp(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'le',
                                            'value': '2012-09-25T11:30:00',
                                            }])
        self.assertEqual(data[0]['sum'], 5)
        self.assertEqual(data[0]['count'], 1)

    def test_end_timestamp_before(self):
        data = self.get_json(self.PATH, q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            },
                                           {'field': 'timestamp',
                                            'op': 'le',
                                            'value': '2012-09-25T09:54:00',
                                            }])
        self.assertEqual(data, [])

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
        self.assertEqual(data[0]['sum'], 6)
        self.assertEqual(data[0]['count'], 1)


class TestGroupByInstance(FunctionalTest,
                          tests_db.MixinTestsWithBackendScenarios):

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
                c,
                self.CONF.publisher.metering_secret,
            )
            self.conn.record_metering_data(msg)

    def test_group_by_user(self):
        data = self.get_json(self.PATH, groupby=['user_id'])
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(groupby_keys_set, set(['user_id']))
        self.assertEqual(groupby_vals_set, set(['user-1', 'user-2', 'user-3']))

        for r in data:
            grp = r['groupby']
            if grp == {'user_id': 'user-1'}:
                self.assertEqual(r['count'], 2)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 2)
                self.assertEqual(r['max'], 2)
                self.assertEqual(r['sum'], 4)
                self.assertEqual(r['avg'], 2)
            elif grp == {'user_id': 'user-2'}:
                self.assertEqual(r['count'], 4)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 1)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 8)
                self.assertEqual(r['avg'], 2)
            elif grp == {'user_id': 'user-3'}:
                self.assertEqual(r['count'], 1)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 4)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 4)
                self.assertEqual(r['avg'], 4)

    def test_group_by_resource(self):
        data = self.get_json(self.PATH, groupby=['resource_id'])
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(groupby_keys_set, set(['resource_id']))
        self.assertEqual(groupby_vals_set, set(['resource-1',
                                                'resource-2',
                                                'resource-3']))

        for r in data:
            grp = r['groupby']
            if grp == {'resource_id': 'resource-1'}:
                self.assertEqual(r['count'], 3)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 2)
                self.assertEqual(r['max'], 2)
                self.assertEqual(r['sum'], 6)
                self.assertEqual(r['avg'], 2)
            elif grp == {'resource_id': 'resource-2'}:
                self.assertEqual(r['count'], 3)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 1)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 6)
                self.assertEqual(r['avg'], 2)
            elif grp == {'resource_id': 'resource-3'}:
                self.assertEqual(r['count'], 1)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 4)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 4)
                self.assertEqual(r['avg'], 4)

    def test_group_by_project(self):
        data = self.get_json(self.PATH, groupby=['project_id'])
        groupby_keys_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].keys())
        groupby_vals_set = set(x for sub_dict in data
                               for x in sub_dict['groupby'].values())
        self.assertEqual(groupby_keys_set, set(['project_id']))
        self.assertEqual(groupby_vals_set, set(['project-1', 'project-2']))

        for r in data:
            grp = r['groupby']
            if grp == {'project_id': 'project-1'}:
                self.assertEqual(r['count'], 5)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 1)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 10)
                self.assertEqual(r['avg'], 2)
            elif grp == {'project_id': 'project-2'}:
                self.assertEqual(r['count'], 2)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 2)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 6)
                self.assertEqual(r['avg'], 3)

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
        self.assertEqual(groupby_keys_set, set(['user_id', 'resource_id']))
        self.assertEqual(groupby_vals_set, set(['user-1', 'user-2',
                                                'user-3', 'resource-1',
                                                'resource-2', 'resource-3']))

        for r in data:
            grp = r['groupby']
            if grp == {'user_id': 'user-1',
                                  'resource_id': 'resource-1'}:
                self.assertEqual(r['count'], 2)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 2)
                self.assertEqual(r['max'], 2)
                self.assertEqual(r['sum'], 4)
                self.assertEqual(r['avg'], 2)
            elif grp == {'user_id': 'user-2',
                         'resource_id': 'resource-1'}:
                self.assertEqual(r['count'], 1)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 2)
                self.assertEqual(r['max'], 2)
                self.assertEqual(r['sum'], 2)
                self.assertEqual(r['avg'], 2)
            elif grp == {'user_id': 'user-2',
                         'resource_id': 'resource-2'}:
                self.assertEqual(r['count'], 3)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 1)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 6)
                self.assertEqual(r['avg'], 2)
            elif grp == {'user_id': 'user-3',
                         'resource_id': 'resource-3'}:
                self.assertEqual(r['count'], 1)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 4)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 4)
                self.assertEqual(r['avg'], 4)
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
        self.assertEqual(groupby_keys_set, set(['resource_id']))
        self.assertEqual(groupby_vals_set, set(['resource-1',
                                                'resource-2',
                                                'resource-3']))

        for r in data:
            grp = r['groupby']
            if grp == {'resource_id': 'resource-1'}:
                self.assertEqual(r['count'], 2)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 2)
                self.assertEqual(r['max'], 2)
                self.assertEqual(r['sum'], 4)
                self.assertEqual(r['avg'], 2)
            elif grp == {'resource_id': 'resource-2'}:
                self.assertEqual(r['count'], 2)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 1)
                self.assertEqual(r['max'], 1)
                self.assertEqual(r['sum'], 2)
                self.assertEqual(r['avg'], 1)
            elif grp == {'resource_id': 'resource-3'}:
                self.assertEqual(r['count'], 1)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 4)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 4)
                self.assertEqual(r['avg'], 4)

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
        self.assertEqual(groupby_keys_set, set(['project_id', 'resource_id']))
        self.assertEqual(groupby_vals_set, set(['project-1', 'project-2',
                                                'resource-1', 'resource-2']))

        for r in data:
            grp = r['groupby']
            if grp == {'project_id': 'project-1',
                       'resource_id': 'resource-1'}:
                self.assertEqual(r['count'], 1)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 2)
                self.assertEqual(r['max'], 2)
                self.assertEqual(r['sum'], 2)
                self.assertEqual(r['avg'], 2)
            elif grp == {'project_id': 'project-1',
                         'resource_id': 'resource-2'}:
                self.assertEqual(r['count'], 2)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 1)
                self.assertEqual(r['max'], 1)
                self.assertEqual(r['sum'], 2)
                self.assertEqual(r['avg'], 1)
            elif grp == {'project_id': 'project-2',
                         'resource_id': 'resource-2'}:
                self.assertEqual(r['count'], 1)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 4)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 4)
                self.assertEqual(r['avg'], 4)
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
        self.assertEqual(groupby_keys_set, set(['project_id']))
        self.assertEqual(groupby_vals_set, set(['project-1', 'project-2']))
        period_start_set = set(sub_dict['period_start'] for sub_dict in data)
        period_start_valid = set([u'2013-08-01T10:11:00',
                                  u'2013-08-01T14:11:00',
                                  u'2013-08-01T16:11:00'])
        self.assertEqual(period_start_set, period_start_valid)

        for r in data:
            grp = r['groupby']
            period_start = r['period_start']
            if (grp == {'project_id': 'project-1'} and
                    period_start == u'2013-08-01T10:11:00'):
                self.assertEqual(r['count'], 3)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 1)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 6)
                self.assertEqual(r['avg'], 2)
                self.assertEqual(r['duration'], 4260)
                self.assertEqual(r['duration_start'], u'2013-08-01T10:11:00')
                self.assertEqual(r['duration_end'], u'2013-08-01T11:22:00')
                self.assertEqual(r['period'], 7200)
                self.assertEqual(r['period_end'], u'2013-08-01T12:11:00')
            elif (grp == {'project_id': 'project-1'} and
                    period_start == u'2013-08-01T14:11:00'):
                self.assertEqual(r['count'], 2)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 2)
                self.assertEqual(r['max'], 2)
                self.assertEqual(r['sum'], 4)
                self.assertEqual(r['avg'], 2)
                self.assertEqual(r['duration'], 4260)
                self.assertEqual(r['duration_start'], u'2013-08-01T14:59:00')
                self.assertEqual(r['duration_end'], u'2013-08-01T16:10:00')
                self.assertEqual(r['period'], 7200)
                self.assertEqual(r['period_end'], u'2013-08-01T16:11:00')
            elif (grp == {'project_id': 'project-2'} and
                    period_start == u'2013-08-01T14:11:00'):
                self.assertEqual(r['count'], 1)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 2)
                self.assertEqual(r['max'], 2)
                self.assertEqual(r['sum'], 2)
                self.assertEqual(r['avg'], 2)
                self.assertEqual(r['duration'], 0)
                self.assertEqual(r['duration_start'], u'2013-08-01T15:37:00')
                self.assertEqual(r['duration_end'], u'2013-08-01T15:37:00')
                self.assertEqual(r['period'], 7200)
                self.assertEqual(r['period_end'], u'2013-08-01T16:11:00')
            elif (grp == {'project_id': 'project-2'} and
                    period_start == u'2013-08-01T16:11:00'):
                self.assertEqual(r['count'], 1)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 4)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 4)
                self.assertEqual(r['avg'], 4)
                self.assertEqual(r['duration'], 0)
                self.assertEqual(r['duration_start'], u'2013-08-01T17:28:00')
                self.assertEqual(r['duration_end'], u'2013-08-01T17:28:00')
                self.assertEqual(r['period'], 7200)
                self.assertEqual(r['period_end'], u'2013-08-01T18:11:00')
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
        self.assertEqual(groupby_keys_set, set(['project_id']))
        self.assertEqual(groupby_vals_set, set(['project-1', 'project-2']))
        period_start_set = set(sub_dict['period_start'] for sub_dict in data)
        period_start_valid = set([u'2013-08-01T10:11:00',
                                  u'2013-08-01T14:11:00',
                                  u'2013-08-01T16:11:00'])
        self.assertEqual(period_start_set, period_start_valid)

        for r in data:
            grp = r['groupby']
            period_start = r['period_start']
            if (grp == {'project_id': 'project-1'} and
                    period_start == u'2013-08-01T10:11:00'):
                self.assertEqual(r['count'], 2)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 1)
                self.assertEqual(r['max'], 1)
                self.assertEqual(r['sum'], 2)
                self.assertEqual(r['avg'], 1)
                self.assertEqual(r['duration'], 1740)
                self.assertEqual(r['duration_start'], u'2013-08-01T10:11:00')
                self.assertEqual(r['duration_end'], u'2013-08-01T10:40:00')
                self.assertEqual(r['period'], 7200)
                self.assertEqual(r['period_end'], u'2013-08-01T12:11:00')
            elif (grp == {'project_id': 'project-1'} and
                    period_start == u'2013-08-01T14:11:00'):
                self.assertEqual(r['count'], 1)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 2)
                self.assertEqual(r['max'], 2)
                self.assertEqual(r['sum'], 2)
                self.assertEqual(r['avg'], 2)
                self.assertEqual(r['duration'], 0)
                self.assertEqual(r['duration_start'], u'2013-08-01T14:59:00')
                self.assertEqual(r['duration_end'], u'2013-08-01T14:59:00')
                self.assertEqual(r['period'], 7200)
                self.assertEqual(r['period_end'], u'2013-08-01T16:11:00')
            elif (grp == {'project_id': 'project-2'} and
                    period_start == u'2013-08-01T16:11:00'):
                self.assertEqual(r['count'], 1)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 4)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 4)
                self.assertEqual(r['avg'], 4)
                self.assertEqual(r['duration'], 0)
                self.assertEqual(r['duration_start'], u'2013-08-01T17:28:00')
                self.assertEqual(r['duration_end'], u'2013-08-01T17:28:00')
                self.assertEqual(r['period'], 7200)
                self.assertEqual(r['period_end'], u'2013-08-01T18:11:00')
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
        self.assertEqual(data, [])

    def test_group_by_end_timestamp_before(self):
        data = self.get_json(self.PATH,
                             q=[{'field': 'timestamp',
                                 'op': 'le',
                                 'value': '2013-08-01T10:10:59'}],
                             groupby=['project_id'])
        self.assertEqual(data, [])

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
        self.assertEqual(groupby_keys_set, set(['project_id']))
        self.assertEqual(groupby_vals_set, set(['project-1', 'project-2']))

        for r in data:
            grp = r['groupby']
            if grp == {'project_id': 'project-1'}:
                self.assertEqual(r['count'], 2)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 2)
                self.assertEqual(r['max'], 2)
                self.assertEqual(r['sum'], 4)
                self.assertEqual(r['avg'], 2)
            elif grp == {'project_id': 'project-2'}:
                self.assertEqual(r['count'], 2)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 2)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 6)
                self.assertEqual(r['avg'], 3)

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
        self.assertEqual(groupby_keys_set, set(['project_id']))
        self.assertEqual(groupby_vals_set, set(['project-1']))

        for r in data:
            grp = r['groupby']
            if grp == {'project_id': 'project-1'}:
                self.assertEqual(r['count'], 3)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 1)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 6)
                self.assertEqual(r['avg'], 2)

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
        self.assertEqual(groupby_keys_set, set(['project_id']))
        self.assertEqual(groupby_vals_set, set(['project-1', 'project-2']))

        for r in data:
            grp = r['groupby']
            if grp == {'project_id': 'project-1'}:
                self.assertEqual(r['count'], 5)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 1)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 10)
                self.assertEqual(r['avg'], 2)
            elif grp == {'project_id': 'project-2'}:
                self.assertEqual(r['count'], 2)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 2)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 6)
                self.assertEqual(r['avg'], 3)

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
        self.assertEqual(groupby_keys_set, set(['resource_id']))
        self.assertEqual(groupby_vals_set, set(['resource-1', 'resource-3']))

        for r in data:
            grp = r['groupby']
            if grp == {'resource_id': 'resource-1'}:
                self.assertEqual(r['count'], 2)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 2)
                self.assertEqual(r['max'], 2)
                self.assertEqual(r['sum'], 4)
                self.assertEqual(r['avg'], 2)
            elif grp == {'resource_id': 'resource-3'}:
                self.assertEqual(r['count'], 1)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 4)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 4)
                self.assertEqual(r['avg'], 4)

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
        self.assertEqual(groupby_keys_set, set(['project_id']))
        self.assertEqual(groupby_vals_set, set(['project-1', 'project-2']))
        period_start_set = set(sub_dict['period_start'] for sub_dict in data)
        period_start_valid = set([u'2013-08-01T14:00:00',
                                  u'2013-08-01T15:00:00',
                                  u'2013-08-01T16:00:00'])
        self.assertEqual(period_start_set, period_start_valid)

        for r in data:
            grp = r['groupby']
            period_start = r['period_start']
            if (grp == {'project_id': 'project-1'} and
                    period_start == u'2013-08-01T14:00:00'):
                self.assertEqual(r['count'], 1)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 2)
                self.assertEqual(r['max'], 2)
                self.assertEqual(r['sum'], 2)
                self.assertEqual(r['avg'], 2)
                self.assertEqual(r['duration'], 0)
                self.assertEqual(r['duration_start'], u'2013-08-01T14:59:00')
                self.assertEqual(r['duration_end'], u'2013-08-01T14:59:00')
                self.assertEqual(r['period'], 3600)
                self.assertEqual(r['period_end'], u'2013-08-01T15:00:00')
            elif (grp == {'project_id': 'project-1'} and
                    period_start == u'2013-08-01T16:00:00'):
                self.assertEqual(r['count'], 1)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 2)
                self.assertEqual(r['max'], 2)
                self.assertEqual(r['sum'], 2)
                self.assertEqual(r['avg'], 2)
                self.assertEqual(r['duration'], 0)
                self.assertEqual(r['duration_start'], u'2013-08-01T16:10:00')
                self.assertEqual(r['duration_end'], u'2013-08-01T16:10:00')
                self.assertEqual(r['period'], 3600)
                self.assertEqual(r['period_end'], u'2013-08-01T17:00:00')
            elif (grp == {'project_id': 'project-2'} and
                    period_start == u'2013-08-01T15:00:00'):
                self.assertEqual(r['count'], 1)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 2)
                self.assertEqual(r['max'], 2)
                self.assertEqual(r['sum'], 2)
                self.assertEqual(r['avg'], 2)
                self.assertEqual(r['duration'], 0)
                self.assertEqual(r['duration_start'], u'2013-08-01T15:37:00')
                self.assertEqual(r['duration_end'], u'2013-08-01T15:37:00')
                self.assertEqual(r['period'], 3600)
                self.assertEqual(r['period_end'], u'2013-08-01T16:00:00')
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
        self.assertEqual(groupby_keys_set, set(['project_id']))
        self.assertEqual(groupby_vals_set, set(['project-1', 'project-2']))
        period_start_set = set(sub_dict['period_start'] for sub_dict in data)
        period_start_valid = set([u'2013-08-01T10:00:00',
                                  u'2013-08-01T14:00:00',
                                  u'2013-08-01T16:00:00'])
        self.assertEqual(period_start_set, period_start_valid)

        for r in data:
            grp = r['groupby']
            period_start = r['period_start']
            if (grp == {'project_id': 'project-1'} and
                    period_start == u'2013-08-01T10:00:00'):
                self.assertEqual(r['count'], 2)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 1)
                self.assertEqual(r['max'], 1)
                self.assertEqual(r['sum'], 2)
                self.assertEqual(r['avg'], 1)
                self.assertEqual(r['duration'], 1740)
                self.assertEqual(r['duration_start'], u'2013-08-01T10:11:00')
                self.assertEqual(r['duration_end'], u'2013-08-01T10:40:00')
                self.assertEqual(r['period'], 7200)
                self.assertEqual(r['period_end'], u'2013-08-01T12:00:00')
            elif (grp == {'project_id': 'project-1'} and
                    period_start == u'2013-08-01T14:00:00'):
                self.assertEqual(r['count'], 1)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 2)
                self.assertEqual(r['max'], 2)
                self.assertEqual(r['sum'], 2)
                self.assertEqual(r['avg'], 2)
                self.assertEqual(r['duration'], 0)
                self.assertEqual(r['duration_start'], u'2013-08-01T14:59:00')
                self.assertEqual(r['duration_end'], u'2013-08-01T14:59:00')
                self.assertEqual(r['period'], 7200)
                self.assertEqual(r['period_end'], u'2013-08-01T16:00:00')
            elif (grp == {'project_id': 'project-2'} and
                    period_start == u'2013-08-01T16:00:00'):
                self.assertEqual(r['count'], 1)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 4)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 4)
                self.assertEqual(r['avg'], 4)
                self.assertEqual(r['duration'], 0)
                self.assertEqual(r['duration_start'], u'2013-08-01T17:28:00')
                self.assertEqual(r['duration_end'], u'2013-08-01T17:28:00')
                self.assertEqual(r['period'], 7200)
                self.assertEqual(r['period_end'], u'2013-08-01T18:00:00')
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


class TestGroupBySource(FunctionalTest,
                        tests_db.MixinTestsWithBackendScenarios):

    # FIXME(terriyu): We have to put test_group_by_source in its own class
    # because SQLAlchemy currently doesn't support group by source statistics.
    # When group by source is supported in SQLAlchemy, this test should be
    # moved to TestGroupByInstance with all the other group by statistics
    # tests.

    scenarios = [
        ('mongodb',
         dict(database_connection=tests_db.MongoDBFakeConnectionUrl())),
        ('hbase', dict(database_connection=tests_db.HBaseFakeConnectionUrl())),
        ('db2', dict(database_connection=tests_db.DB2FakeConnectionUrl())),
    ]

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
                c,
                self.CONF.publisher.metering_secret,
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
        self.assertEqual(groupby_keys_set, set(['source']))
        self.assertEqual(groupby_vals_set, set(['source-1',
                                                'source-2',
                                                'source-3']))

        for r in data:
            grp = r['groupby']
            if grp == {'source': 'source-1'}:
                self.assertEqual(r['count'], 4)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 1)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 8)
                self.assertEqual(r['avg'], 2)
            elif grp == {'source': 'source-2'}:
                self.assertEqual(r['count'], 2)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 2)
                self.assertEqual(r['max'], 2)
                self.assertEqual(r['sum'], 4)
                self.assertEqual(r['avg'], 2)
            elif grp == {'source': 'source-3'}:
                self.assertEqual(r['count'], 1)
                self.assertEqual(r['unit'], 's')
                self.assertEqual(r['min'], 4)
                self.assertEqual(r['max'], 4)
                self.assertEqual(r['sum'], 4)
                self.assertEqual(r['avg'], 4)
