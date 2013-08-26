# Copyright 2013 OpenStack Foundation.
# All Rights Reserved.
# Copyright 2013 IBM Corp.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
"""Test the methods related to query."""
import datetime

import wsme

from ceilometer import storage
from ceilometer.api.controllers import v2 as api
from ceilometer.api.controllers.v2 import Query
from ceilometer.openstack.common import timeutils
from ceilometer.tests import base as tests_base


class TestQuery(tests_base.TestCase):

    def test_get_value_as_type_with_integer(self):
        query = Query(field='metadata.size',
                      op='eq',
                      value='123',
                      type='integer')
        expected = 123
        self.assertEqual(query._get_value_as_type(), expected)

    def test_get_value_as_type_with_float(self):
        query = Query(field='metadata.size',
                      op='eq',
                      value='123.456',
                      type='float')
        expected = 123.456
        self.assertEqual(query._get_value_as_type(), expected)

    def test_get_value_as_type_with_boolean(self):
        query = Query(field='metadata.is_public',
                      op='eq',
                      value='True',
                      type='boolean')
        expected = True
        self.assertEqual(query._get_value_as_type(), expected)

    def test_get_value_as_type_with_string(self):
        query = Query(field='metadata.name',
                      op='eq',
                      value='linux',
                      type='string')
        expected = 'linux'
        self.assertEqual(query._get_value_as_type(), expected)

    def test_get_value_as_type_with_integer_without_type(self):
        query = Query(field='metadata.size',
                      op='eq',
                      value='123')
        expected = 123
        self.assertEqual(query._get_value_as_type(), expected)

    def test_get_value_as_type_with_float_without_type(self):
        query = Query(field='metadata.size',
                      op='eq',
                      value='123.456')
        expected = 123.456
        self.assertEqual(query._get_value_as_type(), expected)

    def test_get_value_as_type_with_boolean_without_type(self):
        query = Query(field='metadata.is_public',
                      op='eq',
                      value='True')
        expected = True
        self.assertEqual(query._get_value_as_type(), expected)

    def test_get_value_as_type_with_string_without_type(self):
        query = Query(field='metadata.name',
                      op='eq',
                      value='linux')
        expected = 'linux'
        self.assertEqual(query._get_value_as_type(), expected)

    def test_get_value_as_type_with_bad_type(self):
        query = Query(field='metadata.size',
                      op='eq',
                      value='123.456',
                      type='blob')
        self.assertRaises(wsme.exc.ClientSideError, query._get_value_as_type)

    def test_get_value_as_type_with_bad_value(self):
        query = Query(field='metadata.size',
                      op='eq',
                      value='fake',
                      type='integer')
        self.assertRaises(wsme.exc.ClientSideError, query._get_value_as_type)

    def test_get_value_as_type_integer_expression_without_type(self):
        # bug 1221736
        query = Query(field='should_be_a_string',
                      op='eq',
                      value='123-1')
        expected = '123-1'
        self.assertEqual(query._get_value_as_type(), expected)

    def test_get_value_as_type_boolean_expression_without_type(self):
        # bug 1221736
        query = Query(field='should_be_a_string',
                      op='eq',
                      value='True or False')
        expected = 'True or False'
        self.assertEqual(query._get_value_as_type(), expected)

    def test_get_value_as_type_with_syntax_error(self):
        # bug 1221736
        value = 'WWW-Layer-4a80714f-0232-4580-aa5e-81494d1a4147-uolhh25p5xxm'
        query = Query(field='group_id',
                      op='eq',
                      value=value)
        expected = value
        self.assertEqual(query._get_value_as_type(), expected)

    def test_get_value_as_type_with_syntax_error_colons(self):
        # bug 1221736
        value = 'Ref::StackId'
        query = Query(field='field_name',
                      op='eq',
                      value=value)
        expected = value
        self.assertEqual(query._get_value_as_type(), expected)


class TestValidateGroupByFields(tests_base.TestCase):

    def test_valid_field(self):
        result = api._validate_groupby_fields(['user_id'])
        self.assertEqual(result, ['user_id'])

    def test_valid_fields_multiple(self):
        result = set(
            api._validate_groupby_fields(['user_id', 'project_id', 'source'])
        )
        self.assertEqual(result, set(['user_id', 'project_id', 'source']))

    def test_invalid_field(self):
        self.assertRaises(wsme.exc.UnknownArgument,
                          api._validate_groupby_fields,
                          ['wtf'])

    def test_invalid_field_multiple(self):
        self.assertRaises(wsme.exc.UnknownArgument,
                          api._validate_groupby_fields,
                          ['user_id', 'wtf', 'project_id', 'source'])

    def test_duplicate_fields(self):
        result = set(
            api._validate_groupby_fields(['user_id', 'source', 'user_id'])
        )
        self.assertEqual(result, set(['user_id', 'source']))


class TestQueryToKwArgs(tests_base.TestCase):
    def setUp(self):
        super(TestQueryToKwArgs, self).setUp()
        self.stubs.Set(api, '_sanitize_query', lambda x, y, **z: x)

    def test_sample_filter_single(self):
        q = [Query(field='user_id',
                   op='eq',
                   value='uid')]
        kwargs = api._query_to_kwargs(q, storage.SampleFilter.__init__)
        self.assertIn('user', kwargs)
        self.assertEqual(len(kwargs), 1)
        self.assertEqual(kwargs['user'], 'uid')

    def test_sample_filter_multi(self):
        q = [Query(field='user_id',
                   op='eq',
                   value='uid'),
             Query(field='project_id',
                   op='eq',
                   value='pid'),
             Query(field='resource_id',
                   op='eq',
                   value='rid'),
             Query(field='source',
                   op='eq',
                   value='source_name'),
             Query(field='meter',
                   op='eq',
                   value='meter_name')]
        kwargs = api._query_to_kwargs(q, storage.SampleFilter.__init__)
        self.assertEqual(len(kwargs), 5)
        self.assertEqual(kwargs['user'], 'uid')
        self.assertEqual(kwargs['project'], 'pid')
        self.assertEqual(kwargs['resource'], 'rid')
        self.assertEqual(kwargs['source'], 'source_name')
        self.assertEqual(kwargs['meter'], 'meter_name')

    def test_sample_filter_timestamp(self):
        ts_start = timeutils.utcnow()
        ts_end = ts_start + datetime.timedelta(minutes=5)
        q = [Query(field='timestamp',
                   op='lt',
                   value=str(ts_end)),
             Query(field='timestamp',
                   op='gt',
                   value=str(ts_start))]
        kwargs = api._query_to_kwargs(q, storage.SampleFilter.__init__)
        self.assertEqual(len(kwargs), 4)
        self.assertEqual(kwargs['start'], ts_start)
        self.assertEqual(kwargs['end'], ts_end)
        self.assertEqual(kwargs['start_timestamp_op'], 'gt')
        self.assertEqual(kwargs['end_timestamp_op'], 'lt')

    def test_sample_filter_meta(self):
        q = [Query(field='metadata.size',
                   op='eq',
                   value='20'),
             Query(field='resource_metadata.id',
                   op='eq',
                   value='meta_id')]
        kwargs = api._query_to_kwargs(q, storage.SampleFilter.__init__)
        self.assertEqual(len(kwargs), 1)
        self.assertEqual(len(kwargs['metaquery']), 2)
        self.assertEqual(kwargs['metaquery']['metadata.size'], 20)
        self.assertEqual(kwargs['metaquery']['metadata.id'], 'meta_id')

    def test_sample_filter_non_equality_on_metadata(self):
        queries = [Query(field='resource_metadata.image_id',
                         op='gt',
                         value='image',
                         type='string'),
                   Query(field='metadata.ramdisk_id',
                         op='le',
                         value='ramdisk',
                         type='string')]
        self.assertRaises(
            wsme.exc.InvalidInput,
            api._query_to_kwargs,
            queries,
            storage.SampleFilter.__init__,
            headers={'X-ProjectId': 'foobar'})

    def test_sample_filter_invalid_field(self):
        q = [Query(field='invalid',
                   op='eq',
                   value='20')]
        self.assertRaises(
            wsme.exc.UnknownArgument,
            api._query_to_kwargs, q, storage.SampleFilter.__init__)

    def test_sample_filter_invalid_op(self):
        q = [Query(field='user_id',
                   op='lt',
                   value='20')]
        self.assertRaises(
            wsme.exc.InvalidInput,
            api._query_to_kwargs, q, storage.SampleFilter.__init__)

    def test_sample_filter_timestamp_invalid_op(self):
        ts_start = timeutils.utcnow()
        q = [Query(field='timestamp',
                   op='eq',
                   value=str(ts_start))]
        self.assertRaises(
            wsme.exc.InvalidInput,
            api._query_to_kwargs, q, storage.SampleFilter.__init__)

    def test_sample_filter_exclude_internal(self):
        queries = [Query(field=f,
                         op='eq',
                         value='fake',
                         type='string') for f in ['y', 'on_behalf_of', 'x']]
        self.assertRaises(wsme.exc.ClientSideError,
                          api._query_to_kwargs,
                          queries,
                          storage.SampleFilter.__init__,
                          headers={'X-ProjectId': 'foobar'},
                          internal_keys=['on_behalf_of'])

    def test_sample_filter_self_always_excluded(self):
        queries = [Query(field='user_id',
                         op='eq',
                         value='20')]
        kwargs = api._query_to_kwargs(queries,
                                      storage.SampleFilter.__init__,
                                      headers={'X-ProjectId': 'foobar'})
        self.assertFalse('self' in kwargs)

    def test_sample_filter_translation(self):
        queries = [Query(field=f,
                         op='eq',
                         value='fake_%s' % f,
                         type='string') for f in ['user_id',
                                                  'project_id',
                                                  'resource_id']]
        kwargs = api._query_to_kwargs(queries,
                                      storage.SampleFilter.__init__,
                                      headers={'X-ProjectId': 'foobar'})
        for o in ['user', 'project', 'resource']:
            self.assertEqual(kwargs.get(o), 'fake_%s_id' % o)
