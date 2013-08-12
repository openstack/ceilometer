# -*- encoding: utf-8 -*-
#
# Copyright 2012 Red Hat, Inc.
#
# Author: Angus Salkeld <asalkeld@redhat.com>
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
"""Test listing meters.
"""

import datetime
import logging
import testscenarios

from oslo.config import cfg

from ceilometer.publisher import rpc
from ceilometer import sample
from ceilometer.tests import db as tests_db

from .base import FunctionalTest

load_tests = testscenarios.load_tests_apply_scenarios

LOG = logging.getLogger(__name__)


class TestListEmptyMeters(FunctionalTest,
                          tests_db.MixinTestsWithBackendScenarios):

    def test_empty(self):
        data = self.get_json('/meters')
        self.assertEquals([], data)


class TestListMeters(FunctionalTest,
                     tests_db.MixinTestsWithBackendScenarios):

    def setUp(self):
        super(TestListMeters, self).setUp()

        for cnt in [
                sample.Sample(
                    'meter.test',
                    'cumulative',
                    '',
                    1,
                    'user-id',
                    'project-id',
                    'resource-id',
                    timestamp=datetime.datetime(2012, 7, 2, 10, 40),
                    resource_metadata={'display_name': 'test-server',
                                       'tag': 'self.counter'},
                    source='test_source'),
                sample.Sample(
                    'meter.test',
                    'cumulative',
                    '',
                    3,
                    'user-id',
                    'project-id',
                    'resource-id',
                    timestamp=datetime.datetime(2012, 7, 2, 11, 40),
                    resource_metadata={'display_name': 'test-server',
                                       'tag': 'self.counter1'},
                    source='test_source'),
                sample.Sample(
                    'meter.mine',
                    'gauge',
                    '',
                    1,
                    'user-id',
                    'project-id',
                    'resource-id2',
                    timestamp=datetime.datetime(2012, 7, 2, 10, 41),
                    resource_metadata={'display_name': 'test-server',
                                       'tag': 'self.counter2'},
                    source='test_source'),
                sample.Sample(
                    'meter.test',
                    'cumulative',
                    '',
                    1,
                    'user-id2',
                    'project-id2',
                    'resource-id3',
                    timestamp=datetime.datetime(2012, 7, 2, 10, 42),
                    resource_metadata={'display_name': 'test-server',
                                       'tag': 'self.counter3'},
                    source='test_source'),
                sample.Sample(
                    'meter.mine',
                    'gauge',
                    '',
                    1,
                    'user-id4',
                    'project-id2',
                    'resource-id4',
                    timestamp=datetime.datetime(2012, 7, 2, 10, 43),
                    resource_metadata={'display_name': 'test-server',
                                       'tag': 'self.counter4',
                                       'properties': {
                                       'prop_1': 'prop_value',
                                       'prop_2': {'sub_prop_1':
                                                  'sub_prop_value'}}
                                       },
                    source='test_source')]:
            msg = rpc.meter_message_from_counter(
                cnt,
                cfg.CONF.publisher_rpc.metering_secret)
            self.conn.record_metering_data(msg)

    def test_list_meters(self):
        data = self.get_json('/meters')
        self.assertEquals(4, len(data))
        self.assertEquals(set(r['resource_id'] for r in data),
                          set(['resource-id',
                               'resource-id2',
                               'resource-id3',
                               'resource-id4']))
        self.assertEquals(set(r['name'] for r in data),
                          set(['meter.test',
                               'meter.mine']))

    def test_list_meters_with_dict_metadata(self):
        data = self.get_json('/meters/meter.mine',
                             q=[{'field':
                                 'metadata.properties.prop_2.sub_prop_1',
                                 'op': 'eq',
                                 'value': 'sub_prop_value',
                                 }])
        self.assertEquals(1, len(data))
        self.assertEquals('resource-id4', data[0]['resource_id'])
        metadata = data[0]['resource_metadata']
        self.assertIsNotNone(metadata)
        # FIXME (flwang): Based on current implement, the metadata of
        # dictionary type can't be shown in the output. See bug 1203699.
        # Will add more asserts in the fix of 1203699.
        self.assertEqual('self.counter4', metadata['tag'])

    def test_list_meters_metadata_query(self):
        data = self.get_json('/meters/meter.test',
                             q=[{'field': 'metadata.tag',
                                 'op': 'eq',
                                 'value': 'self.counter1',
                                 }],)
        self.assertEquals(1, len(data))
        self.assertEquals(set(r['resource_id'] for r in data),
                          set(['resource-id']))
        self.assertEquals(set(r['counter_name'] for r in data),
                          set(['meter.test']))

    def test_list_meters_multi_metadata_query(self):
        data = self.get_json('/meters/meter.test',
                             q=[{'field': 'metadata.tag',
                                 'op': 'eq',
                                 'value': 'self.counter1',
                                 },
                                {'field': 'metadata.display_name',
                                 'op': 'eq',
                                 'value': 'test-server',
                                 }],)
        self.assertEquals(1, len(data))
        self.assertEquals(set(r['resource_id'] for r in data),
                          set(['resource-id']))
        self.assertEquals(set(r['counter_name'] for r in data),
                          set(['meter.test']))

    def test_with_resource(self):
        data = self.get_json('/meters', q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            }])
        ids = set(r['name'] for r in data)
        self.assertEquals(set(['meter.test']), ids)

    def test_with_resource_and_metadata_query(self):
        data = self.get_json('/meters/meter.mine',
                             q=[{'field': 'resource_id',
                                 'op': 'eq',
                                 'value': 'resource-id2',
                                 },
                                {'field': 'metadata.tag',
                                 'op': 'eq',
                                 'value': 'self.counter2',
                                 }])
        self.assertEquals(1, len(data))
        self.assertEquals(set(r['resource_id'] for r in data),
                          set(['resource-id2']))
        self.assertEquals(set(r['counter_name'] for r in data),
                          set(['meter.mine']))

    def test_with_source(self):
        data = self.get_json('/meters', q=[{'field': 'source',
                                            'value': 'test_source',
                                            }])
        ids = set(r['resource_id'] for r in data)
        self.assertEquals(set(['resource-id',
                               'resource-id2',
                               'resource-id3',
                               'resource-id4']), ids)

    def test_with_source_and_metadata_query(self):
        data = self.get_json('/meters/meter.mine',
                             q=[{'field': 'source',
                                 'op': 'eq',
                                 'value': 'test_source',
                                 },
                                {'field': 'metadata.tag',
                                 'op': 'eq',
                                 'value': 'self.counter2',
                                 }])
        self.assertEquals(1, len(data))
        self.assertEquals(set(r['source'] for r in data),
                          set(['test_source']))
        self.assertEquals(set(r['counter_name'] for r in data),
                          set(['meter.mine']))

    def test_with_source_non_existent(self):
        data = self.get_json('/meters',
                             q=[{'field': 'source',
                                 'value': 'test_source_doesnt_exist',
                                 }],
                             )
        assert not data

    def test_with_user(self):
        data = self.get_json('/meters',
                             q=[{'field': 'user_id',
                                 'value': 'user-id',
                                 }],
                             )

        uids = set(r['user_id'] for r in data)
        self.assertEquals(set(['user-id']), uids)

        nids = set(r['name'] for r in data)
        self.assertEquals(set(['meter.mine', 'meter.test']), nids)

        rids = set(r['resource_id'] for r in data)
        self.assertEquals(set(['resource-id', 'resource-id2']), rids)

    def test_with_user_and_metadata_query(self):
        data = self.get_json('/meters/meter.test',
                             q=[{'field': 'user_id',
                                 'op': 'eq',
                                 'value': 'user-id',
                                 },
                                {'field': 'metadata.tag',
                                 'op': 'eq',
                                 'value': 'self.counter1',
                                 }])
        self.assertEquals(1, len(data))
        self.assertEquals(set(r['user_id'] for r in data),
                          set(['user-id']))
        self.assertEquals(set(r['counter_name'] for r in data),
                          set(['meter.test']))

    def test_with_user_non_existent(self):
        data = self.get_json('/meters',
                             q=[{'field': 'user_id',
                                 'value': 'user-id-foobar123',
                                 }],
                             )
        self.assertEquals(data, [])

    def test_with_project(self):
        data = self.get_json('/meters',
                             q=[{'field': 'project_id',
                                 'value': 'project-id2',
                                 }],
                             )
        ids = set(r['resource_id'] for r in data)
        self.assertEquals(set(['resource-id3', 'resource-id4']), ids)

    def test_with_project_and_metadata_query(self):
        data = self.get_json('/meters/meter.test',
                             q=[{'field': 'project_id',
                                 'op': 'eq',
                                 'value': 'project-id',
                                 },
                                {'field': 'metadata.tag',
                                 'op': 'eq',
                                 'value': 'self.counter1',
                                 }])
        self.assertEquals(1, len(data))
        self.assertEquals(set(r['project_id'] for r in data),
                          set(['project-id']))
        self.assertEquals(set(r['counter_name'] for r in data),
                          set(['meter.test']))

    def test_with_project_non_existent(self):
        data = self.get_json('/meters',
                             q=[{'field': 'project_id',
                                 'value': 'jd-was-here',
                                 }],
                             )
        self.assertEquals(data, [])
