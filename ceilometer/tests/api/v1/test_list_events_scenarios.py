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
"""Test listing raw events.
"""

import datetime
import testscenarios

from ceilometer.publisher import utils
from ceilometer import sample

from ceilometer.tests import api as tests_api
from ceilometer.tests import db as tests_db

load_tests = testscenarios.load_tests_apply_scenarios


class TestListEvents(tests_api.TestBase,
                     tests_db.MixinTestsWithBackendScenarios):

    def setUp(self):
        super(TestListEvents, self).setUp()
        for cnt in [
                sample.Sample(
                    'instance',
                    'cumulative',
                    '',
                    1,
                    'user-id',
                    'project1',
                    'resource-id',
                    timestamp=datetime.datetime(2012, 7, 2, 10, 40),
                    resource_metadata={'display_name': 'test-server',
                                       'tag': 'self.sample'},
                    source='source1',
                ),
                sample.Sample(
                    'instance',
                    'cumulative',
                    '',
                    2,
                    'user-id',
                    'project1',
                    'resource-id',
                    timestamp=datetime.datetime(2012, 7, 2, 10, 41),
                    resource_metadata={'display_name': 'test-server',
                                       'tag': 'self.sample'},
                    source='source1',
                ),
                sample.Sample(
                    'instance',
                    'cumulative',
                    '',
                    1,
                    'user-id2',
                    'project2',
                    'resource-id-alternate',
                    timestamp=datetime.datetime(2012, 7, 2, 10, 42),
                    resource_metadata={'display_name': 'test-server',
                                       'tag': 'self.sample2'},
                    source='source1',
                ),
        ]:
            msg = utils.meter_message_from_counter(
                cnt,
                self.CONF.publisher.metering_secret)
            self.conn.record_metering_data(msg)

    def test_empty_project(self):
        data = self.get('/projects/no-such-project/meters/instance')
        self.assertEqual({'events': []}, data)

    def test_by_project(self):
        data = self.get('/projects/project1/meters/instance')
        self.assertEqual(2, len(data['events']))

    def test_by_project_non_admin(self):
        data = self.get('/projects/project1/meters/instance',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project1"})
        self.assertEqual(2, len(data['events']))

    def test_by_project_wrong_tenant(self):
        resp = self.get('/projects/project1/meters/instance',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "this-is-my-project"})
        self.assertEqual(404, resp.status_code)

    def test_by_project_with_timestamps(self):
        data = self.get('/projects/project1/meters/instance',
                        start_timestamp=datetime.datetime(2012, 7, 2, 10, 42))
        self.assertEqual(0, len(data['events']))

    def test_empty_resource(self):
        data = self.get('/resources/no-such-resource/meters/instance')
        self.assertEqual({'events': []}, data)

    def test_by_resource(self):
        data = self.get('/resources/resource-id/meters/instance')
        self.assertEqual(2, len(data['events']))

    def test_by_resource_non_admin(self):
        data = self.get('/resources/resource-id-alternate/meters/instance',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project2"})
        self.assertEqual(1, len(data['events']))

    def test_by_resource_some_tenant(self):
        data = self.get('/resources/resource-id/meters/instance',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project2"})
        self.assertEqual(0, len(data['events']))

    def test_empty_source(self):
        data = self.get('/sources/no-such-source/meters/instance')
        self.assertEqual({'events': []}, data)

    def test_by_source(self):
        data = self.get('/sources/source1/meters/instance')
        self.assertEqual(3, len(data['events']))

    def test_by_source_non_admin(self):
        data = self.get('/sources/source1/meters/instance',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project2"})
        self.assertEqual(1, len(data['events']))

    def test_by_source_with_timestamps(self):
        data = self.get('/sources/source1/meters/instance',
                        end_timestamp=datetime.datetime(2012, 7, 2, 10, 42))
        self.assertEqual(2, len(data['events']))

    def test_empty_user(self):
        data = self.get('/users/no-such-user/meters/instance')
        self.assertEqual({'events': []}, data)

    def test_by_user(self):
        data = self.get('/users/user-id/meters/instance')
        self.assertEqual(2, len(data['events']))

    def test_by_user_non_admin(self):
        data = self.get('/users/user-id/meters/instance',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project1"})
        self.assertEqual(2, len(data['events']))

    def test_by_user_wrong_tenant(self):
        data = self.get('/users/user-id/meters/instance',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project2"})
        self.assertEqual(0, len(data['events']))

    def test_by_user_with_timestamps(self):
        data = self.get('/users/user-id/meters/instance',
                        start_timestamp=datetime.datetime(2012, 7, 2, 10, 41),
                        end_timestamp=datetime.datetime(2012, 7, 2, 10, 42))
        self.assertEqual(1, len(data['events']))

    def test_template_list_event(self):
        rv = self.get('/resources/resource-id/meters/instance',
                      headers={"Accept": "text/html"})
        self.assertEqual(200, rv.status_code)
        self.assertTrue("text/html" in rv.content_type)


class TestListEventsMetaquery(TestListEvents,
                              tests_db.MixinTestsWithBackendScenarios):

    def test_metaquery1(self):
        q = '/sources/source1/meters/instance'
        data = self.get('%s?metadata.tag=self.sample2' % q)
        self.assertEqual(1, len(data['events']))

    def test_metaquery1_wrong_tenant(self):
        q = '/sources/source1/meters/instance'
        data = self.get('%s?metadata.tag=self.sample2' % q,
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project1"})
        self.assertEqual(0, len(data['events']))

    def test_metaquery2(self):
        q = '/sources/source1/meters/instance'
        data = self.get('%s?metadata.tag=self.sample' % q)
        self.assertEqual(2, len(data['events']))

    def test_metaquery2_non_admin(self):
        q = '/sources/source1/meters/instance'
        data = self.get('%s?metadata.tag=self.sample' % q,
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project1"})
        self.assertEqual(2, len(data['events']))

    def test_metaquery3(self):
        q = '/sources/source1/meters/instance'
        data = self.get('%s?metadata.display_name=test-server' % q)
        self.assertEqual(3, len(data['events']))

    def test_metaquery3_with_project(self):
        q = '/sources/source1/meters/instance'
        data = self.get('%s?metadata.display_name=test-server' % q,
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project2"})
        self.assertEqual(1, len(data['events']))
