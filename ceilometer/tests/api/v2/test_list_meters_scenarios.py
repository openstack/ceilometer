# -*- encoding: utf-8 -*-
#
# Copyright 2012 Red Hat, Inc.
# Copyright 2013 IBM Corp.
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

import base64
import datetime
import json as jsonutils
import logging
import testscenarios
import webtest.app

from ceilometer.publisher import utils
from ceilometer import sample
from ceilometer.tests.api.v2 import FunctionalTest
from ceilometer.tests import db as tests_db

load_tests = testscenarios.load_tests_apply_scenarios

LOG = logging.getLogger(__name__)


class TestListEmptyMeters(FunctionalTest,
                          tests_db.MixinTestsWithBackendScenarios):

    def test_empty(self):
        data = self.get_json('/meters')
        self.assertEqual([], data)


class TestValidateUserInput(FunctionalTest,
                            tests_db.MixinTestsWithBackendScenarios):

    def test_list_meters_query_float_metadata(self):
        self.assertRaises(webtest.app.AppError, self.get_json,
                          '/meters/meter.test',
                          q=[{'field': 'metadata.util',
                          'op': 'eq',
                          'value': '0.7.5',
                          'type': 'float'}])
        self.assertRaises(webtest.app.AppError, self.get_json,
                          '/meters/meter.test',
                          q=[{'field': 'metadata.util',
                          'op': 'eq',
                          'value': 'abacaba',
                          'type': 'boolean'}])
        self.assertRaises(webtest.app.AppError, self.get_json,
                          '/meters/meter.test',
                          q=[{'field': 'metadata.util',
                          'op': 'eq',
                          'value': '45.765',
                          'type': 'integer'}])


class TestListMeters(FunctionalTest,
                     tests_db.MixinTestsWithBackendScenarios):

    def setUp(self):
        super(TestListMeters, self).setUp()
        self.messages = []
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
                                       'tag': 'self.sample',
                                       'size': 123,
                                       'util': 0.75,
                                       'is_public': True},
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
                                       'tag': 'self.sample1',
                                       'size': 0,
                                       'util': 0.47,
                                       'is_public': False},
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
                                       'tag': 'self.sample2',
                                       'size': 456,
                                       'util': 0.64,
                                       'is_public': False},
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
                                       'tag': 'self.sample3',
                                       'size': 0,
                                       'util': 0.75,
                                       'is_public': False},
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
                                       'tag': 'self.sample4',
                                       'properties': {
                                           'prop_1': 'prop_value',
                                           'prop_2': {'sub_prop_1':
                                                      'sub_prop_value'}
                                       },
                                       'size': 0,
                                       'util': 0.58,
                                       'is_public': True},
                    source='test_source1')]:
            msg = utils.meter_message_from_counter(
                cnt,
                self.CONF.publisher.metering_secret)
            self.messages.append(msg)
            self.conn.record_metering_data(msg)

    def test_list_meters(self):
        data = self.get_json('/meters')
        self.assertEqual(4, len(data))
        self.assertEqual(set(r['resource_id'] for r in data),
                         set(['resource-id',
                              'resource-id2',
                              'resource-id3',
                              'resource-id4']))
        self.assertEqual(set(r['name'] for r in data),
                         set(['meter.test', 'meter.mine']))
        self.assertEqual(set(r['source'] for r in data),
                         set(['test_source', 'test_source1']))

    def test_meters_query_with_timestamp(self):
        date_time = datetime.datetime(2012, 7, 2, 10, 41)
        isotime = date_time.isoformat()
        resp = self.get_json('/meters',
                             q=[{'field': 'timestamp',
                                 'op': 'gt',
                                 'value': isotime}],
                             expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(jsonutils.loads(resp.body)['error_message']
                         ['faultstring'],
                         'Unknown argument: "timestamp": '
                         'not valid for this resource')

    def test_list_samples(self):
        resp = self.get_json('/samples',
                             q=[{'field': 'search_offset',
                                 'op': 'eq',
                                 'value': 42}],
                             expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(jsonutils.loads(resp.body)['error_message']
                         ['faultstring'],
                         "Invalid input for field/attribute field. "
                         "Value: 'search_offset'. "
                         "search_offset cannot be used without timestamp")

    def test_query_samples_with_search_offset(self):
        data = self.get_json('/samples')
        self.assertEqual(5, len(data))

    def test_list_meters_with_dict_metadata(self):
        data = self.get_json('/meters/meter.mine',
                             q=[{'field':
                                 'metadata.properties.prop_2.sub_prop_1',
                                 'op': 'eq',
                                 'value': 'sub_prop_value',
                                 }])
        self.assertEqual(1, len(data))
        self.assertEqual('resource-id4', data[0]['resource_id'])
        metadata = data[0]['resource_metadata']
        self.assertIsNotNone(metadata)
        self.assertEqual('self.sample4', metadata['tag'])
        self.assertEqual('prop_value', metadata['properties.prop_1'])

    def test_get_one_sample(self):
        sample_id = self.messages[1]['message_id']
        data = self.get_json('/samples/%s' % sample_id)
        self.assertIn('id', data)
        self.assertEqual(data, {
            u'id': sample_id,
            u'metadata': {u'display_name': u'test-server',
                          u'is_public': u'False',
                          u'size': u'0',
                          u'tag': u'self.sample1',
                          u'util': u'0.47'},
            u'meter': u'meter.test',
            u'project_id': u'project-id',
            u'resource_id': u'resource-id',
            u'timestamp': u'2012-07-02T11:40:00',
            u'type': u'cumulative',
            u'unit': u'',
            u'source': 'test_source',
            u'user_id': u'user-id',
            u'volume': 3.0})

    def test_get_not_existing_sample(self):
        resp = self.get_json('/samples/not_exists', expect_errors=True,
                             status=404)
        self.assertEqual(jsonutils.loads(resp.body)['error_message']
                         ['faultstring'],
                         "Sample not_exists Not Found")

    def test_list_samples_with_dict_metadata(self):
        data = self.get_json('/samples',
                             q=[{'field':
                                 'metadata.properties.prop_2.sub_prop_1',
                                 'op': 'eq',
                                 'value': 'sub_prop_value',
                                 }])
        self.assertIn('id', data[0])
        del data[0]['id']  # Randomly generated
        self.assertEqual(data, [{
            u'user_id': u'user-id4',
            u'resource_id': u'resource-id4',
            u'timestamp': u'2012-07-02T10:43:00',
            u'meter': u'meter.mine',
            u'volume': 1.0,
            u'project_id': u'project-id2',
            u'type': u'gauge',
            u'unit': u'',
            u'source': u'test_source1',
            u'metadata': {u'display_name': u'test-server',
                          u'properties.prop_2:sub_prop_1': u'sub_prop_value',
                          u'util': u'0.58',
                          u'tag': u'self.sample4',
                          u'properties.prop_1': u'prop_value',
                          u'is_public': u'True',
                          u'size': u'0'}
        }])

    def test_list_meters_metadata_query(self):
        data = self.get_json('/meters/meter.test',
                             q=[{'field': 'metadata.tag',
                                 'op': 'eq',
                                 'value': 'self.sample1',
                                 }],)
        self.assertEqual(1, len(data))
        self.assertEqual(set(r['resource_id'] for r in data),
                         set(['resource-id']))
        self.assertEqual(set(r['counter_name'] for r in data),
                         set(['meter.test']))

    def test_list_meters_resource_metadata_query(self):
        # NOTE(jd) Same test as above, but with the alias resource_metadata
        # as query field
        data = self.get_json('/meters/meter.test',
                             q=[{'field': 'resource_metadata.tag',
                                 'op': 'eq',
                                 'value': 'self.sample1',
                                 }],)
        self.assertEqual(1, len(data))
        self.assertEqual(set(r['resource_id'] for r in data),
                         set(['resource-id']))
        self.assertEqual(set(r['counter_name'] for r in data),
                         set(['meter.test']))

    def test_list_meters_multi_metadata_query(self):
        data = self.get_json('/meters/meter.test',
                             q=[{'field': 'metadata.tag',
                                 'op': 'eq',
                                 'value': 'self.sample1',
                                 },
                                {'field': 'metadata.display_name',
                                 'op': 'eq',
                                 'value': 'test-server',
                                 }],)
        self.assertEqual(1, len(data))
        self.assertEqual(set(r['resource_id'] for r in data),
                         set(['resource-id']))
        self.assertEqual(set(r['counter_name'] for r in data),
                         set(['meter.test']))

    def test_list_meters_query_integer_metadata(self):
        data = self.get_json('/meters/meter.test',
                             q=[{'field': 'metadata.size',
                             'op': 'eq',
                             'value': '0',
                             'type': 'integer'}]
                             )
        self.assertEqual(2, len(data))
        self.assertEqual(set(r['resource_id'] for r in data),
                         set(['resource-id',
                              'resource-id3']))
        self.assertEqual(set(r['counter_name'] for r in data),
                         set(['meter.test']))
        self.assertEqual(set(r['resource_metadata']['size'] for r in data),
                         set(['0']))

    def test_list_meters_query_float_metadata(self):
        data = self.get_json('/meters/meter.test',
                             q=[{'field': 'metadata.util',
                             'op': 'eq',
                             'value': '0.75',
                             'type': 'float'}]
                             )
        self.assertEqual(2, len(data))
        self.assertEqual(set(r['resource_id'] for r in data),
                         set(['resource-id',
                              'resource-id3']))
        self.assertEqual(set(r['counter_name'] for r in data),
                         set(['meter.test']))
        self.assertEqual(set(r['resource_metadata']['util'] for r in data),
                         set(['0.75']))

    def test_list_meters_query_boolean_metadata(self):
        data = self.get_json('/meters/meter.mine',
                             q=[{'field': 'metadata.is_public',
                             'op': 'eq',
                             'value': 'False',
                             'type': 'boolean'}]
                             )
        self.assertEqual(1, len(data))
        self.assertEqual(set(r['resource_id'] for r in data),
                         set(['resource-id2']))
        self.assertEqual(set(r['counter_name'] for r in data),
                         set(['meter.mine']))
        self.assertEqual(set(r['resource_metadata']['is_public'] for r
                             in data), set(['False']))

    def test_list_meters_query_string_metadata(self):
        data = self.get_json('/meters/meter.test',
                             q=[{'field': 'metadata.tag',
                             'op': 'eq',
                             'value': 'self.sample'}]
                             )
        self.assertEqual(1, len(data))
        self.assertEqual(set(r['resource_id'] for r in data),
                         set(['resource-id']))
        self.assertEqual(set(r['counter_name'] for r in data),
                         set(['meter.test']))
        self.assertEqual(set(r['resource_metadata']['tag'] for r in data),
                         set(['self.sample']))

    def test_list_meters_query_integer_float_metadata_without_type(self):
        data = self.get_json('/meters/meter.test',
                             q=[{'field': 'metadata.size',
                                 'op': 'eq',
                                 'value': '0'},
                                {'field': 'metadata.util',
                                 'op': 'eq',
                                 'value': '0.75'}]
                             )
        self.assertEqual(1, len(data))
        self.assertEqual(set(r['resource_id'] for r in data),
                         set(['resource-id3']))
        self.assertEqual(set(r['counter_name'] for r in data),
                         set(['meter.test']))
        self.assertEqual(set(r['resource_metadata']['size'] for r in data),
                         set(['0']))
        self.assertEqual(set(r['resource_metadata']['util'] for r in data),
                         set(['0.75']))

    def test_with_resource(self):
        data = self.get_json('/meters', q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            }])
        nids = set(r['name'] for r in data)
        self.assertEqual(set(['meter.test']), nids)

        sids = set(r['source'] for r in data)
        self.assertEqual(set(['test_source']), sids)

    def test_with_resource_and_source(self):
        data = self.get_json('/meters', q=[{'field': 'resource_id',
                                            'value': 'resource-id4',
                                            },
                                           {'field': 'source',
                                            'value': 'test_source1',
                                            }])
        nids = set(r['name'] for r in data)
        self.assertEqual(set(['meter.mine']), nids)

        sids = set(r['source'] for r in data)
        self.assertEqual(set(['test_source1']), sids)

    def test_with_resource_and_metadata_query(self):
        data = self.get_json('/meters/meter.mine',
                             q=[{'field': 'resource_id',
                                 'op': 'eq',
                                 'value': 'resource-id2',
                                 },
                                {'field': 'metadata.tag',
                                 'op': 'eq',
                                 'value': 'self.sample2',
                                 }])
        self.assertEqual(1, len(data))
        self.assertEqual(set(r['resource_id'] for r in data),
                         set(['resource-id2']))
        self.assertEqual(set(r['counter_name'] for r in data),
                         set(['meter.mine']))

    def test_with_source(self):
        data = self.get_json('/meters', q=[{'field': 'source',
                                            'value': 'test_source',
                                            }])
        rids = set(r['resource_id'] for r in data)
        self.assertEqual(set(['resource-id',
                              'resource-id2',
                              'resource-id3']), rids)

        sids = set(r['source'] for r in data)
        self.assertEqual(set(['test_source']), sids)

    def test_with_source_and_metadata_query(self):
        data = self.get_json('/meters/meter.mine',
                             q=[{'field': 'source',
                                 'op': 'eq',
                                 'value': 'test_source',
                                 },
                                {'field': 'metadata.tag',
                                 'op': 'eq',
                                 'value': 'self.sample2',
                                 }])
        self.assertEqual(1, len(data))
        self.assertEqual(set(r['source'] for r in data), set(['test_source']))
        self.assertEqual(set(r['counter_name'] for r in data),
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
        self.assertEqual(set(['user-id']), uids)

        nids = set(r['name'] for r in data)
        self.assertEqual(set(['meter.mine', 'meter.test']), nids)

        rids = set(r['resource_id'] for r in data)
        self.assertEqual(set(['resource-id', 'resource-id2']), rids)

        sids = set(r['source'] for r in data)
        self.assertEqual(set(['test_source']), sids)

    def test_with_user_and_source(self):
        data = self.get_json('/meters',
                             q=[{'field': 'user_id',
                                 'value': 'user-id4',
                                 },
                                {'field': 'source',
                                 'value': 'test_source1',
                                 }],
                             )

        uids = set(r['user_id'] for r in data)
        self.assertEqual(set(['user-id4']), uids)

        sids = set(r['source'] for r in data)
        self.assertEqual(set(['test_source1']), sids)

    def test_with_user_and_metadata_query(self):
        data = self.get_json('/meters/meter.test',
                             q=[{'field': 'user_id',
                                 'op': 'eq',
                                 'value': 'user-id',
                                 },
                                {'field': 'metadata.tag',
                                 'op': 'eq',
                                 'value': 'self.sample1',
                                 }])
        self.assertEqual(1, len(data))
        self.assertEqual(set(r['user_id'] for r in data), set(['user-id']))
        self.assertEqual(set(r['counter_name'] for r in data),
                         set(['meter.test']))

    def test_with_user_non_existent(self):
        data = self.get_json('/meters',
                             q=[{'field': 'user_id',
                                 'value': 'user-id-foobar123',
                                 }],
                             )
        self.assertEqual(data, [])

    def test_with_project(self):
        data = self.get_json('/meters',
                             q=[{'field': 'project_id',
                                 'value': 'project-id2',
                                 }],
                             )
        rids = set(r['resource_id'] for r in data)
        self.assertEqual(set(['resource-id3', 'resource-id4']), rids)

        sids = set(r['source'] for r in data)
        self.assertEqual(set(['test_source', 'test_source1']), sids)

    def test_with_project_and_source(self):
        data = self.get_json('/meters',
                             q=[{'field': 'project_id',
                                 'value': 'project-id2',
                                 },
                                {'field': 'source',
                                 'value': 'test_source1',
                                 }],
                             )
        rids = set(r['resource_id'] for r in data)
        self.assertEqual(set(['resource-id4']), rids)

        sids = set(r['source'] for r in data)
        self.assertEqual(set(['test_source1']), sids)

    def test_with_project_and_metadata_query(self):
        data = self.get_json('/meters/meter.test',
                             q=[{'field': 'project_id',
                                 'op': 'eq',
                                 'value': 'project-id',
                                 },
                                {'field': 'metadata.tag',
                                 'op': 'eq',
                                 'value': 'self.sample1',
                                 }])
        self.assertEqual(1, len(data))
        self.assertEqual(set(r['project_id'] for r in data),
                         set(['project-id']))
        self.assertEqual(set(r['counter_name'] for r in data),
                         set(['meter.test']))

    def test_with_project_non_existent(self):
        data = self.get_json('/meters',
                             q=[{'field': 'project_id',
                                 'value': 'jd-was-here',
                                 }],
                             )
        self.assertEqual(data, [])

    def test_list_meters_meter_id(self):
        data = self.get_json('/meters')
        for i in data:
            expected = base64.encodestring('%s+%s' % (i['resource_id'],
                                                      i['name']))
            self.assertEqual(expected, i['meter_id'])
