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

import fixtures
import mock
from oslo_utils import timeutils
from oslotest import base
import wsme

from ceilometer.api.controllers.v2 import base as v2_base
from ceilometer.api.controllers.v2 import meters
from ceilometer.api.controllers.v2 import utils
from ceilometer import storage
from ceilometer.storage import base as storage_base
from ceilometer.tests import base as tests_base


class TestQuery(base.BaseTestCase):
    def setUp(self):
        super(TestQuery, self).setUp()
        self.useFixture(fixtures.MonkeyPatch(
            'pecan.response', mock.MagicMock()))

    def test_get_value_as_type_with_integer(self):
        query = v2_base.Query(field='metadata.size',
                              op='eq',
                              value='123',
                              type='integer')
        expected = 123
        self.assertEqual(expected, query._get_value_as_type())

    def test_get_value_as_type_with_float(self):
        query = v2_base.Query(field='metadata.size',
                              op='eq',
                              value='123.456',
                              type='float')
        expected = 123.456
        self.assertEqual(expected, query._get_value_as_type())

    def test_get_value_as_type_with_boolean(self):
        query = v2_base.Query(field='metadata.is_public',
                              op='eq',
                              value='True',
                              type='boolean')
        expected = True
        self.assertEqual(expected, query._get_value_as_type())

    def test_get_value_as_type_with_string(self):
        query = v2_base.Query(field='metadata.name',
                              op='eq',
                              value='linux',
                              type='string')
        expected = 'linux'
        self.assertEqual(expected, query._get_value_as_type())

    def test_get_value_as_type_with_datetime(self):
        query = v2_base.Query(field='metadata.date',
                              op='eq',
                              value='2014-01-01T05:00:00',
                              type='datetime')
        self.assertIsInstance(query._get_value_as_type(), datetime.datetime)
        self.assertIsNone(query._get_value_as_type().tzinfo)

    def test_get_value_as_type_with_integer_without_type(self):
        query = v2_base.Query(field='metadata.size',
                              op='eq',
                              value='123')
        expected = 123
        self.assertEqual(expected, query._get_value_as_type())

    def test_get_value_as_type_with_float_without_type(self):
        query = v2_base.Query(field='metadata.size',
                              op='eq',
                              value='123.456')
        expected = 123.456
        self.assertEqual(expected, query._get_value_as_type())

    def test_get_value_as_type_with_boolean_without_type(self):
        query = v2_base.Query(field='metadata.is_public',
                              op='eq',
                              value='True')
        expected = True
        self.assertEqual(expected, query._get_value_as_type())

    def test_get_value_as_type_with_string_without_type(self):
        query = v2_base.Query(field='metadata.name',
                              op='eq',
                              value='linux')
        expected = 'linux'
        self.assertEqual(expected, query._get_value_as_type())

    def test_get_value_as_type_with_bad_type(self):
        query = v2_base.Query(field='metadata.size',
                              op='eq',
                              value='123.456',
                              type='blob')
        self.assertRaises(wsme.exc.ClientSideError, query._get_value_as_type)

    def test_get_value_as_type_with_bad_value(self):
        query = v2_base.Query(field='metadata.size',
                              op='eq',
                              value='fake',
                              type='integer')
        self.assertRaises(wsme.exc.ClientSideError, query._get_value_as_type)

    def test_get_value_as_type_integer_expression_without_type(self):
        # bug 1221736
        query = v2_base.Query(field='should_be_a_string',
                              op='eq',
                              value='WWW-Layer-4a80714f')
        expected = 'WWW-Layer-4a80714f'
        self.assertEqual(expected, query._get_value_as_type())

    def test_get_value_as_type_boolean_expression_without_type(self):
        # bug 1221736
        query = v2_base.Query(field='should_be_a_string',
                              op='eq',
                              value='True or False')
        expected = 'True or False'
        self.assertEqual(expected, query._get_value_as_type())

    def test_get_value_as_type_with_syntax_error(self):
        # bug 1221736
        value = 'WWW-Layer-4a80714f-0232-4580-aa5e-81494d1a4147-uolhh25p5xxm'
        query = v2_base.Query(field='group_id',
                              op='eq',
                              value=value)
        expected = value
        self.assertEqual(expected, query._get_value_as_type())

    def test_get_value_as_type_with_syntax_error_colons(self):
        # bug 1221736
        value = 'Ref::StackId'
        query = v2_base.Query(field='field_name',
                              op='eq',
                              value=value)
        expected = value
        self.assertEqual(expected, query._get_value_as_type())


class TestValidateGroupByFields(base.BaseTestCase):

    def test_valid_field(self):
        result = meters._validate_groupby_fields(['user_id'])
        self.assertEqual(['user_id'], result)

    def test_valid_fields_multiple(self):
        result = set(meters._validate_groupby_fields(
            ['user_id', 'project_id', 'source']))
        self.assertEqual(set(['user_id', 'project_id', 'source']), result)

    def test_invalid_field(self):
        self.assertRaises(wsme.exc.UnknownArgument,
                          meters._validate_groupby_fields,
                          ['wtf'])

    def test_invalid_field_multiple(self):
        self.assertRaises(wsme.exc.UnknownArgument,
                          meters._validate_groupby_fields,
                          ['user_id', 'wtf', 'project_id', 'source'])

    def test_duplicate_fields(self):
        result = set(
            meters._validate_groupby_fields(['user_id', 'source', 'user_id'])
        )
        self.assertEqual(set(['user_id', 'source']), result)


class TestQueryToKwArgs(tests_base.BaseTestCase):
    def setUp(self):
        super(TestQueryToKwArgs, self).setUp()
        self.useFixture(fixtures.MockPatchObject(
            utils, 'sanitize_query', side_effect=lambda x, y, **z: x))
        self.useFixture(fixtures.MockPatchObject(
            utils, '_verify_query_segregation', side_effect=lambda x, **z: x))

    def test_sample_filter_single(self):
        q = [v2_base.Query(field='user_id',
                           op='eq',
                           value='uid')]
        kwargs = utils.query_to_kwargs(q, storage.SampleFilter.__init__)
        self.assertIn('user', kwargs)
        self.assertEqual(1, len(kwargs))
        self.assertEqual('uid', kwargs['user'])

    def test_sample_filter_multi(self):
        q = [v2_base.Query(field='user_id',
                           op='eq',
                           value='uid'),
             v2_base.Query(field='project_id',
                           op='eq',
                           value='pid'),
             v2_base.Query(field='resource_id',
                           op='eq',
                           value='rid'),
             v2_base.Query(field='source',
                           op='eq',
                           value='source_name'),
             v2_base.Query(field='meter',
                           op='eq',
                           value='meter_name')]
        kwargs = utils.query_to_kwargs(q, storage.SampleFilter.__init__)
        self.assertEqual(5, len(kwargs))
        self.assertEqual('uid', kwargs['user'])
        self.assertEqual('pid', kwargs['project'])
        self.assertEqual('rid', kwargs['resource'])
        self.assertEqual('source_name', kwargs['source'])
        self.assertEqual('meter_name', kwargs['meter'])

    def test_sample_filter_timestamp(self):
        ts_start = timeutils.utcnow()
        ts_end = ts_start + datetime.timedelta(minutes=5)
        q = [v2_base.Query(field='timestamp',
                           op='lt',
                           value=str(ts_end)),
             v2_base.Query(field='timestamp',
                           op='gt',
                           value=str(ts_start))]
        kwargs = utils.query_to_kwargs(q, storage.SampleFilter.__init__)
        self.assertEqual(4, len(kwargs))
        self.assertTimestampEqual(kwargs['start_timestamp'], ts_start)
        self.assertTimestampEqual(kwargs['end_timestamp'], ts_end)
        self.assertEqual('gt', kwargs['start_timestamp_op'])
        self.assertEqual('lt', kwargs['end_timestamp_op'])

    def test_sample_filter_meta(self):
        q = [v2_base.Query(field='metadata.size',
                           op='eq',
                           value='20'),
             v2_base.Query(field='resource_metadata.id',
                           op='eq',
                           value='meta_id')]
        kwargs = utils.query_to_kwargs(q, storage.SampleFilter.__init__)
        self.assertEqual(1, len(kwargs))
        self.assertEqual(2, len(kwargs['metaquery']))
        self.assertEqual(20, kwargs['metaquery']['metadata.size'])
        self.assertEqual('meta_id', kwargs['metaquery']['metadata.id'])

    def test_sample_filter_non_equality_on_metadata(self):
        queries = [v2_base.Query(field='resource_metadata.image_id',
                                 op='gt',
                                 value='image',
                                 type='string'),
                   v2_base.Query(field='metadata.ramdisk_id',
                                 op='le',
                                 value='ramdisk',
                                 type='string')]
        with mock.patch('pecan.request') as request:
            request.headers.return_value = {'X-ProjectId': 'foobar'}
            self.assertRaises(
                wsme.exc.InvalidInput,
                utils.query_to_kwargs,
                queries,
                storage.SampleFilter.__init__)

    def test_sample_filter_invalid_field(self):
        q = [v2_base.Query(field='invalid',
                           op='eq',
                           value='20')]
        self.assertRaises(
            wsme.exc.UnknownArgument,
            utils.query_to_kwargs, q, storage.SampleFilter.__init__)

    def test_sample_filter_invalid_op(self):
        q = [v2_base.Query(field='user_id',
                           op='lt',
                           value='20')]
        self.assertRaises(
            wsme.exc.InvalidInput,
            utils.query_to_kwargs, q, storage.SampleFilter.__init__)

    def test_sample_filter_timestamp_invalid_op(self):
        ts_start = timeutils.utcnow()
        q = [v2_base.Query(field='timestamp',
                           op='eq',
                           value=str(ts_start))]
        self.assertRaises(
            wsme.exc.InvalidInput,
            utils.query_to_kwargs, q, storage.SampleFilter.__init__)

    def test_sample_filter_exclude_internal(self):
        queries = [v2_base.Query(field=f,
                                 op='eq',
                                 value='fake',
                                 type='string')
                   for f in ['y', 'on_behalf_of', 'x']]
        with mock.patch('pecan.request') as request:
            request.headers.return_value = {'X-ProjectId': 'foobar'}
            self.assertRaises(wsme.exc.ClientSideError,
                              utils.query_to_kwargs,
                              queries,
                              storage.SampleFilter.__init__,
                              internal_keys=['on_behalf_of'])

    def test_sample_filter_self_always_excluded(self):
        queries = [v2_base.Query(field='user_id',
                                 op='eq',
                                 value='20')]
        with mock.patch('pecan.request') as request:
            request.headers.return_value = {'X-ProjectId': 'foobar'}
            kwargs = utils.query_to_kwargs(queries,
                                           storage.SampleFilter.__init__)
            self.assertNotIn('self', kwargs)

    def test_sample_filter_translation(self):
        queries = [v2_base.Query(field=f,
                                 op='eq',
                                 value='fake_%s' % f,
                                 type='string') for f in ['user_id',
                                                          'project_id',
                                                          'resource_id']]
        with mock.patch('pecan.request') as request:
            request.headers.return_value = {'X-ProjectId': 'foobar'}
            kwargs = utils.query_to_kwargs(queries,
                                           storage.SampleFilter.__init__)
            for o in ['user', 'project', 'resource']:
                self.assertEqual('fake_%s_id' % o, kwargs.get(o))

    def test_timestamp_validation(self):
        q = [v2_base.Query(field='timestamp',
                           op='le',
                           value='123')]

        exc = self.assertRaises(
            wsme.exc.InvalidInput,
            utils.query_to_kwargs, q, storage.SampleFilter.__init__)
        expected_exc = wsme.exc.InvalidInput('timestamp', '123',
                                             'invalid timestamp format')
        self.assertEqual(str(expected_exc), str(exc))

    def test_sample_filter_valid_fields(self):
        q = [v2_base.Query(field='abc',
                           op='eq',
                           value='abc')]
        exc = self.assertRaises(
            wsme.exc.UnknownArgument,
            utils.query_to_kwargs, q, storage.SampleFilter.__init__)
        valid_keys = ['message_id', 'meter', 'project', 'resource',
                      'search_offset', 'source', 'timestamp', 'user']
        msg = ("unrecognized field in query: %s, "
               "valid keys: %s") % (q, valid_keys)
        expected_exc = wsme.exc.UnknownArgument('abc', msg)
        self.assertEqual(str(expected_exc), str(exc))

    def test_get_meters_filter_valid_fields(self):
        q = [v2_base.Query(field='abc',
                           op='eq',
                           value='abc')]
        exc = self.assertRaises(
            wsme.exc.UnknownArgument,
            utils.query_to_kwargs,
            q, storage_base.Connection.get_meters, ['limit', 'unique'])
        valid_keys = ['project', 'resource', 'source', 'user']
        msg = ("unrecognized field in query: %s, "
               "valid keys: %s") % (q, valid_keys)
        expected_exc = wsme.exc.UnknownArgument('abc', msg)
        self.assertEqual(str(expected_exc), str(exc))

    def test_get_resources_filter_valid_fields(self):
        q = [v2_base.Query(field='abc',
                           op='eq',
                           value='abc')]
        exc = self.assertRaises(
            wsme.exc.UnknownArgument,
            utils.query_to_kwargs,
            q, storage_base.Connection.get_resources, ['limit'])
        valid_keys = ['project', 'resource',
                      'search_offset', 'source', 'timestamp', 'user']
        msg = ("unrecognized field in query: %s, "
               "valid keys: %s") % (q, valid_keys)
        expected_exc = wsme.exc.UnknownArgument('abc', msg)
        self.assertEqual(str(expected_exc), str(exc))
