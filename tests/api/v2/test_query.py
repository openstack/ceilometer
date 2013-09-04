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

from ceilometer.api.controllers import v2 as api
from ceilometer.api.controllers.v2 import Query
from ceilometer.api.controllers.v2 import _query_to_kwargs
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

    def _fake_db_func(self, resource, on_behalf_of, x, y,
                      metaquery={}, user=None, project=None,
                      start_timestamp=None, start_timestamp_op=None,
                      end_timestamp=None, end_timestamp_op=None, **kwargs):
        pass

    def test_query_to_kwargs_exclude_internal(self):
        queries = [Query(field=f,
                         op='eq',
                         value='fake',
                         type='string') for f in ['y', 'on_behalf_of', 'x']]
        self.assertRaises(wsme.exc.ClientSideError,
                          _query_to_kwargs,
                          queries,
                          self._fake_db_func,
                          headers={'X-ProjectId': 'foobar'},
                          internal_keys=['on_behalf_of'])

    def test_query_to_kwargs_self_always_excluded(self):
        queries = [Query(field=f,
                         op='eq',
                         value='fake',
                         type='string') for f in ['x', 'y']]
        kwargs = _query_to_kwargs(queries,
                                  self._fake_db_func,
                                  headers={'X-ProjectId': 'foobar'})
        self.assertFalse('self' in kwargs)

    def test_query_to_kwargs_timestamp_mapping(self):
        start = datetime.datetime.utcnow()
        end = datetime.datetime.utcnow()
        queries = [Query(field='timestamp',
                         op='gt',
                         value=start.isoformat(),
                         type='string'),
                   Query(field='timestamp',
                         op='le',
                         value=end.isoformat(),
                         type='string')]
        kwargs = _query_to_kwargs(queries,
                                  self._fake_db_func,
                                  headers={'X-ProjectId': 'foobar'})
        self.assertEqual(kwargs.get('start_timestamp'), start)
        self.assertEqual(kwargs.get('start_timestamp_op'), 'gt')
        self.assertEqual(kwargs.get('end_timestamp'), end)
        self.assertEqual(kwargs.get('end_timestamp_op'), 'le')

    def test_query_to_kwargs_non_equality_on_metadata(self):
        queries = [Query(field='resource_metadata.image_id',
                         op='gt',
                         value='image',
                         type='string'),
                   Query(field='metadata.ramdisk_id',
                         op='le',
                         value='ramdisk',
                         type='string')]
        kwargs = _query_to_kwargs(queries,
                                  self._fake_db_func,
                                  headers={'X-ProjectId': 'foobar'})
        self.assertFalse('metaquery' in kwargs)

    def test_query_to_kwargs_equality_on_metadata(self):
        queries = [Query(field='resource_metadata.image_id',
                         op='eq',
                         value='image',
                         type='string'),
                   Query(field='metadata.ramdisk_id',
                         op='eq',
                         value='ramdisk',
                         type='string')]
        kwargs = _query_to_kwargs(queries,
                                  self._fake_db_func,
                                  headers={'X-ProjectId': 'foobar'})
        self.assertTrue('metaquery' in kwargs)
        metaquery = kwargs['metaquery']
        self.assertEqual(metaquery.get('metadata.image_id'), 'image')
        self.assertEqual(metaquery.get('metadata.ramdisk_id'), 'ramdisk')

    def test_query_to_kwargs_translation(self):
        queries = [Query(field=f,
                         op='eq',
                         value='fake_%s' % f,
                         type='string') for f in ['user_id',
                                                  'project_id',
                                                  'resource_id']]
        kwargs = _query_to_kwargs(queries,
                                  self._fake_db_func,
                                  headers={'X-ProjectId': 'foobar'})
        for o in ['user', 'project', 'resource']:
            self.assertEqual(kwargs.get(o), 'fake_%s_id' % o)

    def test_query_to_kwargs_unrecognized(self):
        queries = [Query(field=f,
                         op='eq',
                         value='fake',
                         type='string') for f in ['y', 'z', 'x']]
        self.assertRaises(wsme.exc.ClientSideError,
                          _query_to_kwargs,
                          queries,
                          self._fake_db_func,
                          headers={'X-ProjectId': 'foobar'})


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
