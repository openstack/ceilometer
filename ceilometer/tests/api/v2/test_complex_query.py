# -*- encoding: utf-8 -*-
#
# Copyright Ericsson AB 2013. All rights reserved
#
# Authors: Ildiko Vancsa <ildiko.vancsa@ericsson.com>
#          Balazs Gibizer <balazs.gibizer@ericsson.com>
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
"""Test the methods related to complex query."""
import datetime
import fixtures
import jsonschema
import mock
import wsme

from ceilometer.api.controllers import v2 as api
from ceilometer.openstack.common import test


class FakeComplexQuery(api.ValidatedComplexQuery):
    def __init__(self):
        super(FakeComplexQuery, self).__init__(query=None)


class TestComplexQuery(test.BaseTestCase):
    def setUp(self):
        super(TestComplexQuery, self).setUp()
        self.useFixture(fixtures.MonkeyPatch(
            'pecan.response', mock.MagicMock()))
        self.query = api.ValidatedComplexQuery(FakeComplexQuery())

    def test_replace_isotime_utc(self):
        filter_expr = {"=": {"timestamp": "2013-12-05T19:38:29Z"}}
        self.query._replace_isotime_with_datetime(filter_expr)
        self.assertEqual(datetime.datetime(2013, 12, 5, 19, 38, 29),
                         filter_expr["="]["timestamp"])

    def test_replace_isotime_timezone_removed(self):
        filter_expr = {"=": {"timestamp": "2013-12-05T20:38:29+01:00"}}
        self.query._replace_isotime_with_datetime(filter_expr)
        self.assertEqual(datetime.datetime(2013, 12, 5, 20, 38, 29),
                         filter_expr["="]["timestamp"])

    def test_replace_isotime_wrong_syntax(self):
        filter_expr = {"=": {"timestamp": "not a valid isotime string"}}
        self.assertRaises(wsme.exc.ClientSideError,
                          self.query._replace_isotime_with_datetime,
                          filter_expr)

    def test_replace_isotime_in_complex_filter(self):
        filter_expr = {"and": [{"=": {"timestamp": "2013-12-05T19:38:29Z"}},
                               {"=": {"timestamp": "2013-12-06T19:38:29Z"}}]}
        self.query._replace_isotime_with_datetime(filter_expr)
        self.assertEqual(datetime.datetime(2013, 12, 5, 19, 38, 29),
                         filter_expr["and"][0]["="]["timestamp"])
        self.assertEqual(datetime.datetime(2013, 12, 6, 19, 38, 29),
                         filter_expr["and"][1]["="]["timestamp"])

    def test_replace_isotime_in_complex_filter_with_unbalanced_tree(self):
        subfilter = {"and": [{"=": {"project_id": 42}},
                             {"=": {"timestamp": "2013-12-06T19:38:29Z"}}]}

        filter_expr = {"or": [{"=": {"timestamp": "2013-12-05T19:38:29Z"}},
                              subfilter]}

        self.query._replace_isotime_with_datetime(filter_expr)
        self.assertEqual(datetime.datetime(2013, 12, 5, 19, 38, 29),
                         filter_expr["or"][0]["="]["timestamp"])
        self.assertEqual(datetime.datetime(2013, 12, 6, 19, 38, 29),
                         filter_expr["or"][1]["and"][1]["="]["timestamp"])

    def test_convert_operator_to_lower_case(self):
        filter_expr = {"AND": [{"=": {"project_id": 42}},
                               {"=": {"project_id": 44}}]}
        self.query._convert_operator_to_lower_case(filter_expr)
        self.assertEqual("and", filter_expr.keys()[0])

        filter_expr = {"Or": [{"=": {"project_id": 43}},
                              {"anD": [{"=": {"project_id": 44}},
                                       {"=": {"project_id": 42}}]}]}
        self.query._convert_operator_to_lower_case(filter_expr)
        self.assertEqual("or", filter_expr.keys()[0])
        self.assertEqual("and", filter_expr["or"][1].keys()[0])

    def test_convert_orderby(self):
        orderby = []
        self.query._convert_orderby_to_lower_case(orderby)
        self.assertEqual([], orderby)

        orderby = [{"field1": "DESC"}]
        self.query._convert_orderby_to_lower_case(orderby)
        self.assertEqual([{"field1": "desc"}], orderby)

        orderby = [{"field1": "ASC"}, {"field2": "DESC"}]
        self.query._convert_orderby_to_lower_case(orderby)
        self.assertEqual([{"field1": "asc"}, {"field2": "desc"}], orderby)

    def test_validate_orderby_empty_direction(self):
        orderby = [{"field1": ""}]
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_orderby,
                          orderby)
        orderby = [{"field1": "asc"}, {"field2": ""}]
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_orderby,
                          orderby)

    def test_validate_orderby_wrong_order_string(self):
        orderby = [{"field1": "not a valid order"}]
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_orderby,
                          orderby)

    def test_validate_orderby_wrong_multiple_item_order_string(self):
        orderby = [{"field2": "not a valid order"}, {"field1": "ASC"}]
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_orderby,
                          orderby)


class TestFilterSyntaxValidation(test.BaseTestCase):
    def setUp(self):
        super(TestFilterSyntaxValidation, self).setUp()
        self.query = api.ValidatedComplexQuery(FakeComplexQuery())

    def test_simple_operator(self):
        filter = {"=": {"field_name": "string_value"}}
        self.query._validate_filter(filter)

        filter = {"=>": {"field_name": "string_value"}}
        self.query._validate_filter(filter)

    def test_invalid_simple_operator(self):
        filter = {"==": {"field_name": "string_value"}}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

        filter = {"": {"field_name": "string_value"}}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

    def test_more_than_one_operator_is_invalid(self):
        filter = {"=": {"field_name": "string_value"},
                  "<": {"": ""}}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

    def test_empty_expression_is_invalid(self):
        filter = {}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

    def test_invalid_field_name(self):
        filter = {"=": {"": "value"}}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

        filter = {"=": {" ": "value"}}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

        filter = {"=": {"\t": "value"}}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

    def test_more_than_one_field_is_invalid(self):
        filter = {"=": {"field": "value", "field2": "value"}}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

    def test_missing_field_after_simple_op_is_invalid(self):
        filter = {"=": {}}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

    def test_and_or(self):
        filter = {"and": [{"=": {"field_name": "string_value"}},
                          {"=": {"field2": "value"}}]}
        self.query._validate_filter(filter)

        filter = {"or": [{"and": [{"=": {"field_name": "string_value"}},
                                  {"=": {"field2": "value"}}]},
                         {"=": {"field3": "value"}}]}
        self.query._validate_filter(filter)

        filter = {"or": [{"and": [{"=": {"field_name": "string_value"}},
                                  {"=": {"field2": "value"}},
                                  {"<": {"field3": 42}}]},
                         {"=": {"field3": "value"}}]}
        self.query._validate_filter(filter)

    def test_invalid_complex_operator(self):
        filter = {"xor": [{"=": {"field_name": "string_value"}},
                          {"=": {"field2": "value"}}]}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

    def test_and_or_with_one_child_is_invalid(self):
        filter = {"or": [{"=": {"field_name": "string_value"}}]}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

    def test_complex_operator_with_zero_child_is_invalid(self):
        filter = {"or": []}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

    def test_more_than_one_complex_operator_is_invalid(self):
        filter = {"and": [{"=": {"field_name": "string_value"}},
                          {"=": {"field2": "value"}}],
                  "or": [{"=": {"field_name": "string_value"}},
                         {"=": {"field2": "value"}}]}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)
