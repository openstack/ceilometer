# -*- encoding: utf-8 -*-
#
# Copyright Ericsson AB 2013. All rights reserved
#
# Authors: Ildiko Vancsa <ildiko.vancsa@ericsson.com>
#          Balazs Gibizer <balazs.gibizer@ericsson.com>
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
import logging
import testscenarios

from ceilometer.openstack.common import timeutils
from ceilometer.publisher import utils
from ceilometer import sample
from ceilometer.tests.api import v2 as tests_api
from ceilometer.tests import db as tests_db

load_tests = testscenarios.load_tests_apply_scenarios

LOG = logging.getLogger(__name__)


class TestQueryMetersController(tests_api.FunctionalTest,
                                tests_db.MixinTestsWithBackendScenarios):

    def setUp(self):
        super(TestQueryMetersController, self).setUp()
        self.url = '/query/samples'
        self.admin_header = {"X-Roles": "admin",
                             "X-Project-Id":
                             "project-id1"}
        self.non_admin_header = {"X-Roles": "Member",
                                 "X-Project-Id":
                                 "project-id1"}
        for cnt in [
            sample.Sample('meter.test',
                          'cumulative',
                          '',
                          1,
                          'user-id',
                          'project-id1',
                          'resource-id1',
                          timestamp=datetime.datetime(2012, 7, 2, 10, 40),
                          resource_metadata={'display_name': 'test-server',
                                             'tag': 'self.sample',
                                             'size': 123,
                                             'util': 0.75,
                                             'is_public': True},
                          source='test_source'),
            sample.Sample('meter.test',
                          'cumulative',
                          '',
                          1,
                          'user-id',
                          'project-id2',
                          'resource-id2',
                          timestamp=datetime.datetime(2012, 7, 2, 10, 41),
                          resource_metadata={'display_name': 'test-server',
                                             'tag': 'self.sample',
                                             'size': 123,
                                             'util': 0.75,
                                             'is_public': True},
                          source='test_source')]:

            msg = utils.meter_message_from_counter(
                cnt,
                self.CONF.publisher.metering_secret)
            self.conn.record_metering_data(msg)

    def test_query_fields_are_optional(self):
        data = self.post_json(self.url, params={})
        self.assertEqual(2, len(data.json))

    def test_query_with_isotime(self):
        date_time = datetime.datetime(2012, 7, 2, 10, 41)
        isotime = date_time.isoformat()

        data = self.post_json(self.url,
                              params={"filter":
                                      '{">=": {"timestamp": "'
                                      + isotime + '"}}'})

        self.assertEqual(1, len(data.json))
        for sample in data.json:
            result_time = timeutils.parse_isotime(sample['timestamp'])
            result_time = result_time.replace(tzinfo=None)
            self.assertTrue(result_time >= date_time)

    def test_non_admin_tenant_sees_only_its_own_project(self):
        data = self.post_json(self.url,
                              params={},
                              headers=self.non_admin_header)
        for sample in data.json:
            self.assertEqual("project-id1", sample['project_id'])

    def test_non_admin_tenant_cannot_query_others_project(self):
        data = self.post_json(self.url,
                              params={"filter":
                                      '{"=": {"project_id": "project-id2"}}'},
                              expect_errors=True,
                              headers=self.non_admin_header)

        self.assertEqual(401, data.status_int)
        self.assertIn("Not Authorized to access project project-id2",
                      data.body)

    def test_non_admin_tenant_can_explicitly_filter_for_own_project(self):
        data = self.post_json(self.url,
                              params={"filter":
                                      '{"=": {"project_id": "project-id1"}}'},
                              headers=self.non_admin_header)

        for sample in data.json:
            self.assertEqual("project-id1", sample['project_id'])

    def test_admin_tenant_sees_every_project(self):
        data = self.post_json(self.url,
                              params={},
                              headers=self.admin_header)

        self.assertEqual(2, len(data.json))
        for sample in data.json:
            self.assertIn(sample['project_id'],
                          (["project-id1", "project-id2"]))

    def test_admin_tenant_sees_every_project_with_complex_filter(self):
        filter = ('{"OR": ' +
                  '[{"=": {"project_id": "project-id1"}}, ' +
                  '{"=": {"project_id": "project-id2"}}]}')
        data = self.post_json(self.url,
                              params={"filter": filter},
                              headers=self.admin_header)

        self.assertEqual(2, len(data.json))
        for sample in data.json:
            self.assertIn(sample['project_id'],
                          (["project-id1", "project-id2"]))

    def test_admin_tenant_can_query_any_project(self):
        data = self.post_json(self.url,
                              params={"filter":
                                      '{"=": {"project_id": "project-id2"}}'},
                              headers=self.admin_header)

        self.assertEqual(1, len(data.json))
        for sample in data.json:
            self.assertIn(sample['project_id'], set(["project-id2"]))

    def test_query_with_orderby(self):
        data = self.post_json(self.url,
                              params={"orderby": '[{"project_id": "DESC"}]'})

        self.assertEqual(2, len(data.json))
        self.assertEqual(["project-id2", "project-id1"],
                         [s["project_id"] for s in data.json])

    def test_query_with_lower_and_upper_case_orderby(self):
        data = self.post_json(self.url,
                              params={"orderby": '[{"project_id": "DeSc"}]'})

        self.assertEqual(2, len(data.json))
        self.assertEqual(["project-id2", "project-id1"],
                         [s["project_id"] for s in data.json])

    def test_query_with_missing_order_in_orderby(self):
        data = self.post_json(self.url,
                              params={"orderby": '[{"project_id": ""}]'},
                              expect_errors=True)

        self.assertEqual(500, data.status_int)

    def test_limit_should_be_positive(self):
        data = self.post_json(self.url,
                              params={"limit": 0},
                              expect_errors=True)

        self.assertEqual(400, data.status_int)
        self.assertIn("Limit should be positive", data.body)
