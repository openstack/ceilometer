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
import webtest.app

from ceilometer.publisher import utils
from ceilometer import sample
from ceilometer.tests.api import v2
from ceilometer.tests import db as tests_db


class TestListEmptyMeters(v2.FunctionalTest,
                          tests_db.MixinTestsWithBackendScenarios):

    def test_empty(self):
        data = self.get_json('/meters')
        self.assertEqual([], data)


class TestValidateUserInput(v2.FunctionalTest,
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


class TestListMeters(v2.FunctionalTest,
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
                    'meter.test.new',
                    'cumulative',
                    '',
                    1,
                    'user-id',
                    'project-id',
                    'resource-id',
                    timestamp=datetime.datetime(2012, 7, 2, 10, 40),
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
                    source='test_source1'),
                sample.Sample(
                    u'meter.accent\xe9\u0437',
                    'gauge',
                    '',
                    1,
                    'user-id4',
                    'project-id2',
                    'resource-id4',
                    timestamp=datetime.datetime(2014, 7, 2, 10, 43),
                    resource_metadata={},
                    source='test_source1')]:
            msg = utils.meter_message_from_counter(
                cnt,
                self.CONF.publisher.metering_secret)
            self.messages.append(msg)
            self.conn.record_metering_data(msg)

    def test_list_meters(self):
        data = self.get_json('/meters')
        self.assertEqual(6, len(data))
        self.assertEqual(set(['resource-id',
                              'resource-id2',
                              'resource-id3',
                              'resource-id4']),
                         set(r['resource_id'] for r in data))
        self.assertEqual(set(['meter.test', 'meter.mine', 'meter.test.new',
                              u'meter.accent\xe9\u0437']),
                         set(r['name'] for r in data))
        self.assertEqual(set(['test_source', 'test_source1']),
                         set(r['source'] for r in data))

    def test_meters_query_with_timestamp(self):
        date_time = datetime.datetime(2012, 7, 2, 10, 41)
        isotime = date_time.isoformat()
        resp = self.get_json('/meters',
                             q=[{'field': 'timestamp',
                                 'op': 'gt',
                                 'value': isotime}],
                             expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertEqual('Unknown argument: "timestamp": '
                         'not valid for this resource',
                         jsonutils.loads(resp.body)['error_message']
                         ['faultstring'])

    def test_list_samples(self):
        data = self.get_json('/samples')
        self.assertEqual(7, len(data))

    def test_query_samples_with_invalid_field_name_and_non_eq_operator(self):
        resp = self.get_json('/samples',
                             q=[{'field': 'non_valid_field_name',
                                 'op': 'gt',
                                 'value': 3}],
                             expect_errors=True)
        resp_string = jsonutils.loads(resp.body)
        fault_string = resp_string['error_message']['faultstring']
        expected_error_message = ('Unknown argument: "non_valid_field_name"'
                                  ': unrecognized field in query: '
                                  '[<Query u\'non_valid_field_name\' '
                                  'gt u\'3\' ')
        self.assertEqual(400, resp.status_code)
        self.assertTrue(fault_string.startswith(expected_error_message))

    def test_query_samples_with_invalid_field_name_and_eq_operator(self):
        resp = self.get_json('/samples',
                             q=[{'field': 'non_valid_field_name',
                                 'op': 'eq',
                                 'value': 3}],
                             expect_errors=True)
        resp_string = jsonutils.loads(resp.body)
        fault_string = resp_string['error_message']['faultstring']
        expected_error_message = ('Unknown argument: "non_valid_field_name"'
                                  ': unrecognized field in query: '
                                  '[<Query u\'non_valid_field_name\' '
                                  'eq u\'3\' ')
        self.assertEqual(400, resp.status_code)
        self.assertTrue(fault_string.startswith(expected_error_message))

    def test_query_samples_with_invalid_operator_and_valid_field_name(self):
        resp = self.get_json('/samples',
                             q=[{'field': 'project_id',
                                 'op': 'lt',
                                 'value': '3'}],
                             expect_errors=True)
        resp_string = jsonutils.loads(resp.body)
        fault_string = resp_string['error_message']['faultstring']
        expected_error_message = ("Invalid input for field/attribute op. " +
                                  "Value: 'lt'. unimplemented operator for" +
                                  " project_id")
        self.assertEqual(400, resp.status_code)
        self.assertEqual(fault_string, expected_error_message)

    def test_list_meters_query_wrong_type_metadata(self):
        resp = self.get_json('/meters/meter.test',
                             q=[{'field': 'metadata.size',
                                 'op': 'eq',
                                 'value': '0',
                                 'type': 'blob'}],
                             expect_errors=True
                             )
        expected_error_message = 'The data type blob is not supported.'
        resp_string = jsonutils.loads(resp.body)
        fault_string = resp_string['error_message']['faultstring']
        self.assertTrue(fault_string.startswith(expected_error_message))

    def test_query_samples_with_search_offset(self):
        resp = self.get_json('/samples',
                             q=[{'field': 'search_offset',
                                 'op': 'eq',
                                 'value': 42}],
                             expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertEqual("Invalid input for field/attribute field. "
                         "Value: 'search_offset'. "
                         "search_offset cannot be used without timestamp",
                         jsonutils.loads(resp.body)['error_message']
                         ['faultstring'])

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
        del data['recorded_at']
        self.assertEqual({
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
            u'volume': 3.0}, data)

    def test_get_not_existing_sample(self):
        resp = self.get_json('/samples/not_exists', expect_errors=True,
                             status=404)
        self.assertEqual("Sample not_exists Not Found",
                         jsonutils.loads(resp.body)['error_message']
                         ['faultstring'])

    def test_list_samples_with_dict_metadata(self):
        data = self.get_json('/samples',
                             q=[{'field':
                                 'metadata.properties.prop_2.sub_prop_1',
                                 'op': 'eq',
                                 'value': 'sub_prop_value',
                                 }])
        self.assertIn('id', data[0])
        del data[0]['id']  # Randomly generated
        del data[0]['recorded_at']
        self.assertEqual([{
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
        }], data)

    def test_list_meters_metadata_query(self):
        data = self.get_json('/meters/meter.test',
                             q=[{'field': 'metadata.tag',
                                 'op': 'eq',
                                 'value': 'self.sample1',
                                 }],)
        self.assertEqual(1, len(data))
        self.assertEqual(set(['resource-id']),
                         set(r['resource_id'] for r in data))
        self.assertEqual(set(['meter.test']),
                         set(r['counter_name'] for r in data))

    def test_list_meters_resource_metadata_query(self):
        # NOTE(jd) Same test as above, but with the alias resource_metadata
        # as query field
        data = self.get_json('/meters/meter.test',
                             q=[{'field': 'resource_metadata.tag',
                                 'op': 'eq',
                                 'value': 'self.sample1',
                                 }],)
        self.assertEqual(1, len(data))
        self.assertEqual(set(['resource-id']),
                         set(r['resource_id'] for r in data))
        self.assertEqual(set(['meter.test']),
                         set(r['counter_name'] for r in data))

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
        self.assertEqual(set(['resource-id']),
                         set(r['resource_id'] for r in data))
        self.assertEqual(set(['meter.test']),
                         set(r['counter_name'] for r in data))

    def test_list_meters_query_integer_metadata(self):
        data = self.get_json('/meters/meter.test',
                             q=[{'field': 'metadata.size',
                                 'op': 'eq',
                                 'value': '0',
                                 'type': 'integer'}]
                             )
        self.assertEqual(2, len(data))
        self.assertEqual(set(['resource-id',
                              'resource-id3']),
                         set(r['resource_id'] for r in data))
        self.assertEqual(set(['meter.test']),
                         set(r['counter_name'] for r in data))
        self.assertEqual(set(['0']),
                         set(r['resource_metadata']['size'] for r in data))

    def test_list_meters_query_float_metadata(self):
        data = self.get_json('/meters/meter.test',
                             q=[{'field': 'metadata.util',
                                 'op': 'eq',
                                 'value': '0.75',
                                 'type': 'float'}]
                             )
        self.assertEqual(2, len(data))
        self.assertEqual(set(['resource-id',
                              'resource-id3']),
                         set(r['resource_id'] for r in data))
        self.assertEqual(set(['meter.test']),
                         set(r['counter_name'] for r in data))
        self.assertEqual(set(['0.75']),
                         set(r['resource_metadata']['util'] for r in data))

    def test_list_meters_query_boolean_metadata(self):
        data = self.get_json('/meters/meter.mine',
                             q=[{'field': 'metadata.is_public',
                                 'op': 'eq',
                                 'value': 'False',
                                 'type': 'boolean'}]
                             )
        self.assertEqual(1, len(data))
        self.assertEqual(set(['resource-id2']),
                         set(r['resource_id'] for r in data))
        self.assertEqual(set(['meter.mine']),
                         set(r['counter_name'] for r in data))
        self.assertEqual(set(['False']),
                         set(r['resource_metadata']['is_public']
                             for r in data))

    def test_list_meters_query_string_metadata(self):
        data = self.get_json('/meters/meter.test',
                             q=[{'field': 'metadata.tag',
                                 'op': 'eq',
                                 'value': 'self.sample'}]
                             )
        self.assertEqual(1, len(data))
        self.assertEqual(set(['resource-id']),
                         set(r['resource_id'] for r in data))
        self.assertEqual(set(['meter.test']),
                         set(r['counter_name'] for r in data))
        self.assertEqual(set(['self.sample']),
                         set(r['resource_metadata']['tag'] for r in data))

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
        self.assertEqual(set(['resource-id3']),
                         set(r['resource_id'] for r in data))
        self.assertEqual(set(['meter.test']),
                         set(r['counter_name'] for r in data))
        self.assertEqual(set(['0']),
                         set(r['resource_metadata']['size'] for r in data))
        self.assertEqual(set(['0.75']),
                         set(r['resource_metadata']['util'] for r in data))

    def test_with_resource(self):
        data = self.get_json('/meters', q=[{'field': 'resource_id',
                                            'value': 'resource-id',
                                            }])
        nids = set(r['name'] for r in data)
        self.assertEqual(set(['meter.test', 'meter.test.new']), nids)

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
        self.assertEqual(set(['meter.mine', u'meter.accent\xe9\u0437']), nids)

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
        self.assertEqual(set(['resource-id2']),
                         set(r['resource_id'] for r in data))
        self.assertEqual(set(['meter.mine']),
                         set(r['counter_name'] for r in data))

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
        self.assertEqual(set(['test_source']),
                         set(r['source'] for r in data))
        self.assertEqual(set(['meter.mine']),
                         set(r['counter_name'] for r in data))

    def test_with_source_non_existent(self):
        data = self.get_json('/meters',
                             q=[{'field': 'source',
                                 'value': 'test_source_doesnt_exist',
                                 }],
                             )
        self.assertIsEmpty(data)

    def test_with_user(self):
        data = self.get_json('/meters',
                             q=[{'field': 'user_id',
                                 'value': 'user-id',
                                 }],
                             )

        uids = set(r['user_id'] for r in data)
        self.assertEqual(set(['user-id']), uids)

        nids = set(r['name'] for r in data)
        self.assertEqual(set(['meter.mine', 'meter.test', 'meter.test.new']),
                         nids)

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
        self.assertEqual(set(['user-id']), set(r['user_id'] for r in data))
        self.assertEqual(set(['meter.test']),
                         set(r['counter_name'] for r in data))

    def test_with_user_non_existent(self):
        data = self.get_json('/meters',
                             q=[{'field': 'user_id',
                                 'value': 'user-id-foobar123',
                                 }],
                             )
        self.assertEqual([], data)

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
        self.assertEqual(set(['project-id']),
                         set(r['project_id'] for r in data))
        self.assertEqual(set(['meter.test']),
                         set(r['counter_name'] for r in data))

    def test_with_project_non_existent(self):
        data = self.get_json('/meters',
                             q=[{'field': 'project_id',
                                 'value': 'jd-was-here',
                                 }],
                             )
        self.assertEqual([], data)

    def test_list_meters_meter_id(self):
        data = self.get_json('/meters')
        for i in data:
            meter_id = '%s+%s' % (i['resource_id'], i['name'])
            expected = base64.encodestring(meter_id.encode('utf-8'))
            self.assertEqual(expected, i['meter_id'])
