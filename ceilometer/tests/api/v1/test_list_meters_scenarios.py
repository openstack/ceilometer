# -*- encoding: utf-8 -*-
#
# Copyright 2012 Red Hat, Inc.
#
# Author: Angus Salkeld <asalkeld@redhat.com>
#         Julien Danjou <julien@danjou.info>
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

from ceilometer.publisher import utils
from ceilometer import sample

from ceilometer.tests import api as tests_api
from ceilometer.tests import db as tests_db

load_tests = testscenarios.load_tests_apply_scenarios

LOG = logging.getLogger(__name__)


class TestListEmptyMeters(tests_api.TestBase,
                          tests_db.MixinTestsWithBackendScenarios):

    def test_empty(self):
        data = self.get('/meters')
        self.assertEqual({'meters': []}, data)


class TestListMeters(tests_api.TestBase,
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
                                       'tag': 'self.sample'},
                    source='test_list_resources'),
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
                                       'tag': 'self.sample'},
                    source='test_list_resources'),
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
                                       'tag': 'two.sample'},
                    source='test_list_resources'),
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
                                       'tag': 'three.sample'},
                    source='test_list_resources'),
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
                                       'tag': 'four.sample'},
                    source='test_list_resources')]:
            msg = utils.meter_message_from_counter(
                cnt,
                self.CONF.publisher.metering_secret)
            self.conn.record_metering_data(msg)

    def test_list_meters(self):
        data = self.get('/meters')
        self.assertEqual(4, len(data['meters']))
        self.assertEqual(set(r['resource_id'] for r in data['meters']),
                         set(['resource-id',
                              'resource-id2',
                              'resource-id3',
                              'resource-id4']))
        self.assertEqual(set(r['name'] for r in data['meters']),
                         set(['meter.test', 'meter.mine']))

    def test_list_meters_non_admin(self):
        data = self.get('/meters',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-id"})
        self.assertEqual(2, len(data['meters']))
        self.assertEqual(set(r['resource_id'] for r in data['meters']),
                         set(['resource-id', 'resource-id2']))
        self.assertEqual(set(r['name'] for r in data['meters']),
                         set(['meter.test', 'meter.mine']))

    def test_with_resource(self):
        data = self.get('/resources/resource-id/meters')
        ids = set(r['name'] for r in data['meters'])
        self.assertEqual(set(['meter.test']), ids)

    def test_with_source(self):
        data = self.get('/sources/test_list_resources/meters')
        ids = set(r['resource_id'] for r in data['meters'])
        self.assertEqual(set(['resource-id',
                              'resource-id2',
                              'resource-id3',
                              'resource-id4']), ids)

    def test_with_source_non_admin(self):
        data = self.get('/sources/test_list_resources/meters',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-id2"})
        ids = set(r['resource_id'] for r in data['meters'])
        self.assertEqual(set(['resource-id3', 'resource-id4']), ids)

    def test_with_source_non_existent(self):
        data = self.get('/sources/test_list_resources_dont_exist/meters')
        self.assertEqual(data['meters'], [])

    def test_with_user(self):
        data = self.get('/users/user-id/meters')

        nids = set(r['name'] for r in data['meters'])
        self.assertEqual(set(['meter.mine', 'meter.test']), nids)

        rids = set(r['resource_id'] for r in data['meters'])
        self.assertEqual(set(['resource-id', 'resource-id2']), rids)

    def test_with_user_non_admin(self):
        data = self.get('/users/user-id/meters',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-id"})
        nids = set(r['name'] for r in data['meters'])
        self.assertEqual(set(['meter.mine', 'meter.test']), nids)

        rids = set(r['resource_id'] for r in data['meters'])
        self.assertEqual(set(['resource-id', 'resource-id2']), rids)

    def test_with_user_wrong_tenant(self):
        data = self.get('/users/user-id/meters',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project666"})

        self.assertEqual(data['meters'], [])

    def test_with_user_non_existent(self):
        data = self.get('/users/user-id-foobar123/meters')
        self.assertEqual(data['meters'], [])

    def test_with_project(self):
        data = self.get('/projects/project-id2/meters')
        ids = set(r['resource_id'] for r in data['meters'])
        self.assertEqual(set(['resource-id3', 'resource-id4']), ids)

    def test_with_project_non_admin(self):
        data = self.get('/projects/project-id2/meters',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-id2"})
        ids = set(r['resource_id'] for r in data['meters'])
        self.assertEqual(set(['resource-id3', 'resource-id4']), ids)

    def test_with_project_wrong_tenant(self):
        data = self.get('/projects/project-id2/meters',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-id"})
        self.assertEqual(data.status_code, 404)

    def test_with_project_non_existent(self):
        data = self.get('/projects/jd-was-here/meters')
        self.assertEqual(data['meters'], [])


class TestListMetersMetaquery(TestListMeters,
                              tests_db.MixinTestsWithBackendScenarios):

    def test_metaquery1(self):
        data = self.get('/meters?metadata.tag=self.sample')
        self.assertEqual(1, len(data['meters']))

    def test_metaquery1_non_admin(self):
        data = self.get('/meters?metadata.tag=self.sample',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-id"})
        self.assertEqual(1, len(data['meters']))

    def test_metaquery1_wrong_tenant(self):
        data = self.get('/meters?metadata.tag=self.sample',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-666"})
        self.assertEqual(0, len(data['meters']))

    def test_metaquery2(self):
        data = self.get('/meters?metadata.tag=four.sample')
        self.assertEqual(1, len(data['meters']))

    def test_metaquery2_non_admin(self):
        data = self.get('/meters?metadata.tag=four.sample',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-id2"})
        self.assertEqual(1, len(data['meters']))

    def test_metaquery2_non_admin_wrong_project(self):
        data = self.get('/meters?metadata.tag=four.sample',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-666"})
        self.assertEqual(0, len(data['meters']))
