#
# Copyright Ericsson AB 2013. All rights reserved
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
"""Tests complex queries for samples
"""

import datetime

from oslo_utils import timeutils

from ceilometer.publisher import utils
from ceilometer import sample
from ceilometer.tests.functional.api import v2 as tests_api


admin_header = {"X-Roles": "admin",
                "X-Project-Id":
                "project-id1"}
non_admin_header = {"X-Roles": "Member",
                    "X-Project-Id":
                    "project-id1"}


class TestQueryMetersController(tests_api.FunctionalTest):
    def setUp(self):
        super(TestQueryMetersController, self).setUp()
        self.url = '/query/samples'

        for cnt in [
            sample.Sample('meter.test',
                          'cumulative',
                          '',
                          1,
                          'user-id1',
                          'project-id1',
                          'resource-id1',
                          timestamp=datetime.datetime(2012, 7, 2, 10, 40),
                          resource_metadata={'display_name': 'test-server1',
                                             'tag': 'self.sample',
                                             'size': 456,
                                             'util': 0.25,
                                             'is_public': True},
                          source='test_source'),
            sample.Sample('meter.test',
                          'cumulative',
                          '',
                          2,
                          'user-id2',
                          'project-id2',
                          'resource-id2',
                          timestamp=datetime.datetime(2012, 7, 2, 10, 41),
                          resource_metadata={'display_name': 'test-server2',
                                             'tag': 'self.sample',
                                             'size': 123,
                                             'util': 0.75,
                                             'is_public': True},
                          source='test_source'),
            sample.Sample('meter.test',
                          'cumulative',
                          '',
                          3,
                          'user-id3',
                          'project-id3',
                          'resource-id3',
                          timestamp=datetime.datetime(2012, 7, 2, 10, 42),
                          resource_metadata={'display_name': 'test-server3',
                                             'tag': 'self.sample',
                                             'size': 789,
                                             'util': 0.95,
                                             'is_public': True},
                          source='test_source')]:

            msg = utils.meter_message_from_counter(
                cnt, self.CONF.publisher.telemetry_secret)
            self.conn.record_metering_data(msg)

    def test_query_fields_are_optional(self):
        data = self.post_json(self.url, params={})
        self.assertEqual(3, len(data.json))

    def test_query_with_isotime(self):
        date_time = datetime.datetime(2012, 7, 2, 10, 41)
        isotime = date_time.isoformat()

        data = self.post_json(self.url,
                              params={"filter":
                                      '{">=": {"timestamp": "'
                                      + isotime + '"}}'})

        self.assertEqual(2, len(data.json))
        for sample_item in data.json:
            result_time = timeutils.parse_isotime(sample_item['timestamp'])
            result_time = result_time.replace(tzinfo=None)
            self.assertGreaterEqual(result_time, date_time)

    def test_non_admin_tenant_sees_only_its_own_project(self):
        data = self.post_json(self.url,
                              params={},
                              headers=non_admin_header)
        for sample_item in data.json:
            self.assertEqual("project-id1", sample_item['project_id'])

    def test_non_admin_tenant_cannot_query_others_project(self):
        data = self.post_json(self.url,
                              params={"filter":
                                      '{"=": {"project_id": "project-id2"}}'},
                              expect_errors=True,
                              headers=non_admin_header)

        self.assertEqual(401, data.status_int)
        self.assertIn(b"Not Authorized to access project project-id2",
                      data.body)

    def test_non_admin_tenant_can_explicitly_filter_for_own_project(self):
        data = self.post_json(self.url,
                              params={"filter":
                                      '{"=": {"project_id": "project-id1"}}'},
                              headers=non_admin_header)

        for sample_item in data.json:
            self.assertEqual("project-id1", sample_item['project_id'])

    def test_admin_tenant_sees_every_project(self):
        data = self.post_json(self.url,
                              params={},
                              headers=admin_header)

        self.assertEqual(3, len(data.json))
        for sample_item in data.json:
            self.assertIn(sample_item['project_id'],
                          (["project-id1", "project-id2", "project-id3"]))

    def test_admin_tenant_sees_every_project_with_complex_filter(self):
        filter = ('{"OR": ' +
                  '[{"=": {"project_id": "project-id1"}}, ' +
                  '{"=": {"project_id": "project-id2"}}]}')
        data = self.post_json(self.url,
                              params={"filter": filter},
                              headers=admin_header)

        self.assertEqual(2, len(data.json))
        for sample_item in data.json:
            self.assertIn(sample_item['project_id'],
                          (["project-id1", "project-id2"]))

    def test_admin_tenant_sees_every_project_with_in_filter(self):
        filter = ('{"In": ' +
                  '{"project_id": ["project-id1", "project-id2"]}}')
        data = self.post_json(self.url,
                              params={"filter": filter},
                              headers=admin_header)

        self.assertEqual(2, len(data.json))
        for sample_item in data.json:
            self.assertIn(sample_item['project_id'],
                          (["project-id1", "project-id2"]))

    def test_admin_tenant_can_query_any_project(self):
        data = self.post_json(self.url,
                              params={"filter":
                                      '{"=": {"project_id": "project-id2"}}'},
                              headers=admin_header)

        self.assertEqual(1, len(data.json))
        for sample_item in data.json:
            self.assertIn(sample_item['project_id'], set(["project-id2"]))

    def test_query_with_orderby(self):
        data = self.post_json(self.url,
                              params={"orderby": '[{"project_id": "DESC"}]'})

        self.assertEqual(3, len(data.json))
        self.assertEqual(["project-id3", "project-id2", "project-id1"],
                         [s["project_id"] for s in data.json])

    def test_query_with_field_name_project(self):
        data = self.post_json(self.url,
                              params={"filter":
                                      '{"=": {"project": "project-id2"}}'})

        self.assertEqual(1, len(data.json))
        for sample_item in data.json:
            self.assertIn(sample_item['project_id'], set(["project-id2"]))

    def test_query_with_field_name_resource(self):
        data = self.post_json(self.url,
                              params={"filter":
                                      '{"=": {"resource": "resource-id2"}}'})

        self.assertEqual(1, len(data.json))
        for sample_item in data.json:
            self.assertIn(sample_item['resource_id'], set(["resource-id2"]))

    def test_query_with_wrong_field_name(self):
        data = self.post_json(self.url,
                              params={"filter":
                                      '{"=": {"unknown": "resource-id2"}}'},
                              expect_errors=True)

        self.assertEqual(400, data.status_int)
        self.assertIn(b"is not valid under any of the given schemas",
                      data.body)

    def test_query_with_wrong_json(self):
        data = self.post_json(self.url,
                              params={"filter":
                                      '{"=": "resource": "resource-id2"}}'},
                              expect_errors=True)

        self.assertEqual(400, data.status_int)
        self.assertIn(b"Filter expression not valid", data.body)

    def test_query_with_field_name_user(self):
        data = self.post_json(self.url,
                              params={"filter":
                                      '{"=": {"user": "user-id2"}}'})

        self.assertEqual(1, len(data.json))
        for sample_item in data.json:
            self.assertIn(sample_item['user_id'], set(["user-id2"]))

    def test_query_with_field_name_meter(self):
        data = self.post_json(self.url,
                              params={"filter":
                                      '{"=": {"meter": "meter.test"}}'})

        self.assertEqual(3, len(data.json))
        for sample_item in data.json:
            self.assertIn(sample_item['meter'], set(["meter.test"]))

    def test_query_with_lower_and_upper_case_orderby(self):
        data = self.post_json(self.url,
                              params={"orderby": '[{"project_id": "DeSc"}]'})

        self.assertEqual(3, len(data.json))
        self.assertEqual(["project-id3", "project-id2", "project-id1"],
                         [s["project_id"] for s in data.json])

    def test_query_with_user_field_name_orderby(self):
        data = self.post_json(self.url,
                              params={"orderby": '[{"user": "aSc"}]'})

        self.assertEqual(3, len(data.json))
        self.assertEqual(["user-id1", "user-id2", "user-id3"],
                         [s["user_id"] for s in data.json])

    def test_query_with_volume_field_name_orderby(self):
        data = self.post_json(self.url,
                              params={"orderby": '[{"volume": "deSc"}]'})

        self.assertEqual(3, len(data.json))
        self.assertEqual([3, 2, 1],
                         [s["volume"] for s in data.json])

    def test_query_with_missing_order_in_orderby(self):
        data = self.post_json(self.url,
                              params={"orderby": '[{"project_id": ""}]'},
                              expect_errors=True)

        self.assertEqual(400, data.status_int)
        self.assertIn(b"does not match '(?i)^asc$|^desc$'", data.body)

    def test_query_with_wrong_json_in_orderby(self):
        data = self.post_json(self.url,
                              params={"orderby": '{"project_id": "desc"}]'},
                              expect_errors=True)

        self.assertEqual(400, data.status_int)
        self.assertIn(b"Order-by expression not valid: Extra data", data.body)

    def test_filter_with_metadata(self):
        data = self.post_json(self.url,
                              params={"filter":
                                      '{">=": {"metadata.util": 0.5}}'})

        self.assertEqual(2, len(data.json))
        for sample_item in data.json:
            self.assertGreaterEqual(float(sample_item["metadata"]["util"]),
                                    0.5)

    def test_filter_with_negation(self):
        filter_expr = '{"not": {">=": {"metadata.util": 0.5}}}'
        data = self.post_json(self.url,
                              params={"filter": filter_expr})

        self.assertEqual(1, len(data.json))
        for sample_item in data.json:
            self.assertLess(float(sample_item["metadata"]["util"]), 0.5)

    def test_limit_must_be_positive(self):
        data = self.post_json(self.url,
                              params={"limit": 0},
                              expect_errors=True)

        self.assertEqual(400, data.status_int)
        self.assertIn(b"Limit must be positive", data.body)

    def test_default_limit(self):
        self.CONF.set_override('default_api_return_limit', 1, group='api')
        data = self.post_json(self.url, params={})
        self.assertEqual(1, len(data.json))
