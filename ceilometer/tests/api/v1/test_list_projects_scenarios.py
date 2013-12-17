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
"""Test listing users.
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


class TestListEmptyProjects(tests_api.TestBase,
                            tests_db.MixinTestsWithBackendScenarios):

    def test_empty(self):
        data = self.get('/projects')
        self.assertEqual({'projects': []}, data)


class TestListProjects(tests_api.TestBase,
                       tests_db.MixinTestsWithBackendScenarios):

    def setUp(self):
        super(TestListProjects, self).setUp()
        sample1 = sample.Sample(
            'instance',
            'cumulative',
            'instance',
            1,
            'user-id',
            'project-id',
            'resource-id',
            timestamp=datetime.datetime(2012, 7, 2, 10, 40),
            resource_metadata={'display_name': 'test-server',
                               'tag': 'self.sample'},
            source='test_list_projects',
        )
        msg = utils.meter_message_from_counter(
            sample1,
            self.CONF.publisher.metering_secret,
        )
        self.conn.record_metering_data(msg)

        sample2 = sample.Sample(
            'instance',
            'cumulative',
            'instance',
            1,
            'user-id2',
            'project-id2',
            'resource-id-alternate',
            timestamp=datetime.datetime(2012, 7, 2, 10, 41),
            resource_metadata={'display_name': 'test-server',
                               'tag': 'self.sample2'},
            source='test_list_users',
        )
        msg2 = utils.meter_message_from_counter(
            sample2,
            self.CONF.publisher.metering_secret,
        )
        self.conn.record_metering_data(msg2)

    def test_projects(self):
        data = self.get('/projects')
        self.assertEqual(['project-id', 'project-id2'], data['projects'])

    def test_projects_non_admin(self):
        data = self.get('/projects',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-id"})
        self.assertEqual(['project-id'], data['projects'])

    def test_with_source(self):
        data = self.get('/sources/test_list_users/projects')
        self.assertEqual(['project-id2'], data['projects'])

    def test_with_source_non_admin(self):
        data = self.get('/sources/test_list_users/projects',
                        headers={"X-Roles": "Member",
                                 "X-Project-Id": "project-id2"})
        self.assertEqual(['project-id2'], data['projects'])
