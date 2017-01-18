#
# Copyright Ericsson AB 2013. All rights reserved
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
from oslotest import base
import wsme

from ceilometer.api.controllers.v2 import query
from ceilometer.storage import models


class FakeComplexQuery(query.ValidatedComplexQuery):
    def __init__(self, db_model, additional_name_mapping=None, metadata=False):
        super(FakeComplexQuery, self).__init__(query=None,
                                               db_model=db_model,
                                               additional_name_mapping=(
                                                   additional_name_mapping or
                                                   {}),
                                               metadata_allowed=metadata)


sample_name_mapping = {"resource": "resource_id",
                       "meter": "counter_name",
                       "type": "counter_type",
                       "unit": "counter_unit",
                       "volume": "counter_volume"}


class TestComplexQuery(base.BaseTestCase):
    def setUp(self):
        super(TestComplexQuery, self).setUp()
        self.useFixture(fixtures.MonkeyPatch(
            'pecan.response', mock.MagicMock()))
        self.query = FakeComplexQuery(models.Sample,
                                      sample_name_mapping,
                                      True)

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
        self.assertEqual("and", list(filter_expr.keys())[0])

        filter_expr = {"Or": [{"=": {"project_id": 43}},
                              {"anD": [{"=": {"project_id": 44}},
                                       {"=": {"project_id": 42}}]}]}
        self.query._convert_operator_to_lower_case(filter_expr)
        self.assertEqual("or", list(filter_expr.keys())[0])
        self.assertEqual("and", list(filter_expr["or"][1].keys())[0])

    def test_invalid_filter_misstyped_field_name_samples(self):
        filter = {"=": {"project_id11": 42}}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

    def test_invalid_complex_filter_wrong_field_names(self):
        filter = {"and":
                  [{"=": {"non_existing_field": 42}},
                   {"=": {"project_id": 42}}]}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

        filter = {"or":
                  [{"=": {"non_existing_field": 42}},
                   {"and":
                    [{"=": {"project_id": 44}},
                     {"=": {"project_id": 42}}]}]}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

    def test_convert_orderby(self):
        orderby = []
        self.query._convert_orderby_to_lower_case(orderby)
        self.assertEqual([], orderby)

        orderby = [{"project_id": "DESC"}]
        self.query._convert_orderby_to_lower_case(orderby)
        self.assertEqual([{"project_id": "desc"}], orderby)

        orderby = [{"project_id": "ASC"}, {"resource_id": "DESC"}]
        self.query._convert_orderby_to_lower_case(orderby)
        self.assertEqual([{"project_id": "asc"}, {"resource_id": "desc"}],
                         orderby)

    def test_validate_orderby_empty_direction(self):
        orderby = [{"project_id": ""}]
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_orderby,
                          orderby)
        orderby = [{"project_id": "asc"}, {"resource_id": ""}]
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_orderby,
                          orderby)

    def test_validate_orderby_wrong_order_string(self):
        orderby = [{"project_id": "not a valid order"}]
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_orderby,
                          orderby)

    def test_validate_orderby_wrong_multiple_item_order_string(self):
        orderby = [{"project_id": "not a valid order"}, {"resource_id": "ASC"}]
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_orderby,
                          orderby)

    def test_validate_orderby_empty_field_name(self):
        orderby = [{"": "ASC"}]
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_orderby,
                          orderby)
        orderby = [{"project_id": "asc"}, {"": "desc"}]
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_orderby,
                          orderby)

    def test_validate_orderby_wrong_field_name(self):
        orderby = [{"project_id11": "ASC"}]
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_orderby,
                          orderby)

    def test_validate_orderby_wrong_field_name_multiple_item_orderby(self):
        orderby = [{"project_id": "asc"}, {"resource_id11": "ASC"}]
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_orderby,
                          orderby)

    def test_validate_orderby_metadata_is_not_allowed(self):
        orderby = [{"metadata.display_name": "asc"}]
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_orderby,
                          orderby)


class TestFilterSyntaxValidation(base.BaseTestCase):
    def setUp(self):
        super(TestFilterSyntaxValidation, self).setUp()
        self.query = FakeComplexQuery(models.Sample,
                                      sample_name_mapping,
                                      True)

    def test_simple_operator(self):
        filter = {"=": {"project_id": "string_value"}}
        self.query._validate_filter(filter)

        filter = {"=>": {"project_id": "string_value"}}
        self.query._validate_filter(filter)

    def test_valid_value_types(self):
        valid_values = ["string_value", 42, 3.14, True, False]
        for valid_value in valid_values:
            filter = {"=": {"project_id": valid_value}}
            self.query._validate_filter(filter)

    def test_invalid_simple_operator(self):
        invalid_operators = ["==", ""]
        for invalid_operator in invalid_operators:
            filter = {invalid_operator: {"project_id": "string_value"}}
            self.assertRaises(jsonschema.ValidationError,
                              self.query._validate_filter,
                              filter)

    def test_more_than_one_operator_is_invalid(self):
        filter = {"=": {"project_id": "string_value"},
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
        invalid_names = ["", " ", "\t"]
        for invalid_name in invalid_names:
            filter = {"=": {invalid_name: "value"}}
            self.assertRaises(jsonschema.ValidationError,
                              self.query._validate_filter,
                              filter)

    def test_more_than_one_field_is_invalid(self):
        filter = {"=": {"project_id": "value", "resource_id": "value"}}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

    def test_missing_field_after_simple_op_is_invalid(self):
        filter = {"=": {}}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

    def test_and_or(self):
        filter = {"and": [{"=": {"project_id": "string_value"}},
                          {"=": {"resource_id": "value"}}]}
        self.query._validate_filter(filter)

        filter = {"or": [{"and": [{"=": {"project_id": "string_value"}},
                                  {"=": {"resource_id": "value"}}]},
                         {"=": {"counter_name": "value"}}]}
        self.query._validate_filter(filter)

        filter = {"or": [{"and": [{"=": {"project_id": "string_value"}},
                                  {"=": {"resource_id": "value"}},
                                  {"<": {"counter_name": 42}}]},
                         {"=": {"counter_name": "value"}}]}
        self.query._validate_filter(filter)

    def test_complex_operator_with_in(self):
        filter = {"and": [{"<": {"counter_volume": 42}},
                          {">=": {"counter_volume": 36}},
                          {"in": {"project_id": ["project_id1",
                                                 "project_id2",
                                                 "project_id3"]}}]}
        self.query._validate_filter(filter)

    def test_invalid_complex_operator(self):
        filter = {"xor": [{"=": {"project_id": "string_value"}},
                          {"=": {"resource_id": "value"}}]}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

    def test_and_or_with_one_child_is_invalid(self):
        filter = {"or": [{"=": {"project_id": "string_value"}}]}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

    def test_complex_operator_with_zero_child_is_invalid(self):
        filter = {"or": []}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

    def test_more_than_one_complex_operator_is_invalid(self):
        filter = {"and": [{"=": {"project_id": "string_value"}},
                          {"=": {"resource_id": "value"}}],
                  "or": [{"=": {"project_id": "string_value"}},
                         {"=": {"resource_id": "value"}}]}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

    def test_not(self):
        filter = {"not": {"=": {"project_id": "value"}}}
        self.query._validate_filter(filter)

        filter = {
            "not":
            {"or":
             [{"and":
               [{"=": {"project_id": "string_value"}},
                {"=": {"resource_id": "value"}},
                {"<": {"counter_name": 42}}]},
              {"=": {"counter_name": "value"}}]}}
        self.query._validate_filter(filter)

    def test_not_with_zero_child_is_invalid(self):
        filter = {"not": {}}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

    def test_not_with_more_than_one_child_is_invalid(self):
        filter = {"not": {"=": {"project_id": "value"},
                          "!=": {"resource_id": "value"}}}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)

    def test_empty_in_query_not_passing(self):
        filter = {"in": {"resource_id": []}}
        self.assertRaises(jsonschema.ValidationError,
                          self.query._validate_filter,
                          filter)
