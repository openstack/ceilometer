# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
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
"""Test listing resources.
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


class TestListEmptyResources(tests_api.TestBase,
                             tests_db.MixinTestsWithBackendScenarios):

    def test_empty(self):
        data = self.get('/resources')
        self.assertEqual({'resources': []}, data)


class TestListResourcesBase(tests_api.TestBase,
                            tests_db.MixinTestsWithBackendScenarios):

    def setUp(self):
        super(TestListResourcesBase, self).setUp()

        for cnt in [
                sample.Sample(
                    'instance',
                    'cumulative',
                    '',
                    1,
                    'user-id',
                    'project-id',
                    'resource-id',
                    timestamp=datetime.datetime(2012, 7, 2, 10, 40),
                    resource_metadata={'display_name': 'test-server',
                                       'tag': 'self.sample'},
                    source='test_list_resources',
                ),
                sample.Sample(
                    'instance',
                    'cumulative',
                    '',
                    1,
                    'user-id',
                    'project-id',
                    'resource-id-alternate',
                    timestamp=datetime.datetime(2012, 7, 2, 10, 41),
                    resource_metadata={'display_name': 'test-server',
                                       'tag': 'self.sample2'},
                    source='test_list_resources',
                ),
                sample.Sample(
                    'instance',
                    'cumulative',
                    '',
                    1,
                    'user-id2',
                    'project-id2',
                    'resource-id2',
                    timestamp=datetime.datetime(2012, 7, 2, 10, 42),
                    resource_metadata={'display_name': 'test-server',
                                       'tag': 'self.sample3'},
                    source='test_list_resources',
                ),
                sample.Sample(
                    'instance',
                    'cumulative',
                    '',
                    1,
                    'user-id',
                    'project-id',
                    'resource-id',
                    timestamp=datetime.datetime(2012, 7, 2, 10, 43),
                    resource_metadata={'display_name': 'test-server',
                                       'tag': 'self.sample4'},
                    source='test_list_resources',
                )]:
            msg = utils.meter_message_from_counter(
                cnt,
                self.CONF.publisher.metering_secret)
            self.conn.record_metering_data(msg)


class TestListResources(TestListResourcesBase):

    def test_list_resources(self):
        data = self.get('/resources')
        self.assertEqual(3, len(data['resources']))
        self.assertEqual(set(r['resource_id'] for r in data['resources']),
                         set(['resource-id',
                              'resource-id-alternate',
                              'resource-id2']))

    def test_list_resources_non_admin(self):
        data = self.get('/resources',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-id"})
        self.assertEqual(2, len(data['resources']))
        self.assertEqual(set(r['resource_id'] for r in data['resources']),
                         set(['resource-id', 'resource-id-alternate']))

    def test_list_resources_with_timestamps(self):
        data = self.get('/resources',
                        start_timestamp=datetime.datetime(
                            2012, 7, 2, 10, 41).isoformat(),
                        end_timestamp=datetime.datetime(
                            2012, 7, 2, 10, 43).isoformat())
        self.assertEqual(set(r['resource_id'] for r in data['resources']),
                         set(['resource-id-alternate', 'resource-id2']))

    def test_list_resources_with_timestamps_non_admin(self):
        data = self.get('/resources',
                        start_timestamp=datetime.datetime(
                            2012, 7, 2, 10, 41).isoformat(),
                        end_timestamp=datetime.datetime(
                            2012, 7, 2, 10, 43).isoformat(),
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-id"})
        self.assertEqual(set(r['resource_id'] for r in data['resources']),
                         set(['resource-id-alternate']))

    def test_with_source(self):
        data = self.get('/sources/test_list_resources/resources')
        ids = set(r['resource_id'] for r in data['resources'])
        self.assertEqual(set(['resource-id',
                              'resource-id2',
                              'resource-id-alternate']), ids)

    def test_with_source_non_admin(self):
        data = self.get('/sources/test_list_resources/resources',
                        headers={"X-Roles": "Member",
                        "X-Project-Id": "project-id"})
        ids = set(r['resource_id'] for r in data['resources'])
        self.assertEqual(set(['resource-id', 'resource-id-alternate']), ids)

    def test_with_source_with_timestamps(self):
        data = self.get('/sources/test_list_resources/resources',
                        start_timestamp=datetime.datetime(
                            2012, 7, 2, 10, 41).isoformat(),
                        end_timestamp=datetime.datetime(
                            2012, 7, 2, 10, 43).isoformat())
        ids = set(r['resource_id'] for r in data['resources'])
        self.assertEqual(set(['resource-id2', 'resource-id-alternate']), ids)

    def test_with_source_with_timestamps_non_admin(self):
        data = self.get('/sources/test_list_resources/resources',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-id"},
                        start_timestamp=datetime.datetime(
                            2012, 7, 2, 10, 41).isoformat(),
                        end_timestamp=datetime.datetime(
                            2012, 7, 2, 10, 43).isoformat())
        ids = set(r['resource_id'] for r in data['resources'])
        self.assertEqual(set(['resource-id-alternate']), ids)

    def test_with_source_non_existent(self):
        data = self.get('/sources/test_list_resources_dont_exist/resources')
        self.assertEqual(data['resources'], [])

    def test_with_user(self):
        data = self.get('/users/user-id/resources')
        ids = set(r['resource_id'] for r in data['resources'])
        self.assertEqual(set(['resource-id', 'resource-id-alternate']), ids)

    def test_with_user_non_admin(self):
        data = self.get('/users/user-id/resources',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-id"})
        ids = set(r['resource_id'] for r in data['resources'])
        self.assertEqual(set(['resource-id', 'resource-id-alternate']), ids)

    def test_with_user_wrong_tenant(self):
        data = self.get('/users/user-id/resources',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-jd"})
        ids = set(r['resource_id'] for r in data['resources'])
        self.assertEqual(set(), ids)

    def test_with_user_with_timestamps(self):
        data = self.get('/users/user-id/resources',
                        start_timestamp=datetime.datetime(
                            2012, 7, 2, 10, 42).isoformat(),
                        end_timestamp=datetime.datetime(
                            2012, 7, 2, 10, 42).isoformat())
        ids = set(r['resource_id'] for r in data['resources'])
        self.assertEqual(set(), ids)

    def test_with_user_with_timestamps_non_admin(self):
        data = self.get('/users/user-id/resources',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-id"},
                        start_timestamp=datetime.datetime(
                            2012, 7, 2, 10, 42).isoformat(),
                        end_timestamp=datetime.datetime(
                            2012, 7, 2, 10, 42).isoformat())
        ids = set(r['resource_id'] for r in data['resources'])
        self.assertEqual(set(), ids)

    def test_with_user_non_existent(self):
        data = self.get('/users/user-id-foobar123/resources')
        self.assertEqual(data['resources'], [])

    def test_with_project(self):
        data = self.get('/projects/project-id/resources')
        ids = set(r['resource_id'] for r in data['resources'])
        self.assertEqual(set(['resource-id', 'resource-id-alternate']), ids)

    def test_with_project_non_admin(self):
        data = self.get('/projects/project-id/resources',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-id"})
        ids = set(r['resource_id'] for r in data['resources'])
        self.assertEqual(set(['resource-id', 'resource-id-alternate']), ids)

    def test_with_project_with_timestamp(self):
        data = self.get('/projects/project-id/resources',
                        start_timestamp=datetime.datetime(
                            2012, 7, 2, 10, 40).isoformat(),
                        end_timestamp=datetime.datetime(
                            2012, 7, 2, 10, 41).isoformat())
        ids = set(r['resource_id'] for r in data['resources'])
        self.assertEqual(set(['resource-id']), ids)

    def test_with_project_with_timestamp_non_admin(self):
        data = self.get('/projects/project-id/resources',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-id"},
                        start_timestamp=datetime.datetime(
                            2012, 7, 2, 10, 40).isoformat(),
                        end_timestamp=datetime.datetime(
                            2012, 7, 2, 10, 41).isoformat())
        ids = set(r['resource_id'] for r in data['resources'])
        self.assertEqual(set(['resource-id']), ids)

    def test_with_project_non_existent(self):
        data = self.get('/projects/jd-was-here/resources')
        self.assertEqual(data['resources'], [])


class TestListResourcesMetaquery(TestListResourcesBase,
                                 tests_db.MixinTestsWithBackendScenarios):

    def test_metaquery1(self):
        q = '/sources/test_list_resources/resources'
        data = self.get('%s?metadata.display_name=test-server' % q)
        self.assertEqual(3, len(data['resources']))

    def test_metaquery1_non_admin(self):
        q = '/sources/test_list_resources/resources'
        data = self.get('%s?metadata.display_name=test-server' % q,
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-id"})
        self.assertEqual(2, len(data['resources']))

    def test_metaquery2(self):
        q = '/sources/test_list_resources/resources'
        data = self.get('%s?metadata.tag=self.sample4' % q)
        self.assertEqual(1, len(data['resources']))

    def test_metaquery2_non_admin(self):
        q = '/sources/test_list_resources/resources'
        data = self.get('%s?metadata.tag=self.sample4' % q,
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-id"})
        self.assertEqual(1, len(data['resources']))
