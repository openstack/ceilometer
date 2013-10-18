# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
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
import logging

import testscenarios
import webtest.app

from ceilometer.publisher import utils
from ceilometer import sample
from ceilometer.tests.api.v2 import FunctionalTest
from ceilometer.tests import db as tests_db


load_tests = testscenarios.load_tests_apply_scenarios

LOG = logging.getLogger(__name__)


class TestListEvents(FunctionalTest,
                     tests_db.MixinTestsWithBackendScenarios):

    def setUp(self):
        super(TestListEvents, self).setUp()
        self.sample1 = sample.Sample(
            'instance',
            'cumulative',
            '',
            1,
            'user-id',
            'project1',
            'resource-id',
            timestamp=datetime.datetime(2012, 7, 2, 10, 40),
            resource_metadata={'display_name': 'test-server',
                               'tag': 'self.sample',
                               'dict_properties': {'key': 'value'},
                               'not_ignored_list': ['returned'],
                               },
            source='test_source',
        )
        msg = utils.meter_message_from_counter(
            self.sample1,
            self.CONF.publisher.metering_secret,
        )
        self.conn.record_metering_data(msg)

        self.sample2 = sample.Sample(
            'instance',
            'cumulative',
            '',
            1,
            'user-id2',
            'project2',
            'resource-id-alternate',
            timestamp=datetime.datetime(2012, 7, 2, 10, 41),
            resource_metadata={'display_name': 'test-server',
                               'tag': 'self.sample2',
                               },
            source='source2',
        )
        msg2 = utils.meter_message_from_counter(
            self.sample2,
            self.CONF.publisher.metering_secret,
        )
        self.conn.record_metering_data(msg2)

    def test_all(self):
        data = self.get_json('/meters/instance')
        self.assertEqual(2, len(data))

    def test_all_trailing_slash(self):
        data = self.get_json('/meters/instance/')
        self.assertEqual(2, len(data))

    def test_all_limit(self):
        data = self.get_json('/meters/instance?limit=1')
        self.assertEqual(1, len(data))

    def test_all_limit_negative(self):
        self.assertRaises(webtest.app.AppError,
                          self.get_json,
                          '/meters/instance?limit=-2')

    def test_all_limit_bigger(self):
        data = self.get_json('/meters/instance?limit=42')
        self.assertEqual(2, len(data))

    def test_empty_project(self):
        data = self.get_json('/meters/instance',
                             q=[{'field': 'project_id',
                                 'value': 'no-such-project',
                                 }])
        self.assertEqual([], data)

    def test_by_project(self):
        data = self.get_json('/meters/instance',
                             q=[{'field': 'project_id',
                                 'value': 'project1',
                                 }])
        self.assertEqual(1, len(data))

    def test_empty_resource(self):
        data = self.get_json('/meters/instance',
                             q=[{'field': 'resource_id',
                                 'value': 'no-such-resource',
                                 }])
        self.assertEqual([], data)

    def test_by_resource(self):
        data = self.get_json('/meters/instance',
                             q=[{'field': 'resource_id',
                                 'value': 'resource-id',
                                 }])
        self.assertEqual(1, len(data))

    def test_empty_source(self):
        data = self.get_json('/meters/instance',
                             q=[{'field': 'source',
                                 'value': 'no-such-source',
                                 }])
        self.assertEqual(0, len(data))

    def test_by_source(self):
        data = self.get_json('/meters/instance',
                             q=[{'field': 'source',
                                 'value': 'test_source',
                                 }])
        self.assertEqual(1, len(data))

    def test_empty_user(self):
        data = self.get_json('/meters/instance',
                             q=[{'field': 'user_id',
                                 'value': 'no-such-user',
                                 }])
        self.assertEqual([], data)

    def test_by_user(self):
        data = self.get_json('/meters/instance',
                             q=[{'field': 'user_id',
                                 'value': 'user-id',
                                 }])
        self.assertEqual(1, len(data))

    def test_metadata(self):
        data = self.get_json('/meters/instance',
                             q=[{'field': 'resource_id',
                                 'value': 'resource-id',
                                 }])
        sample = data[0]
        self.assertIn('resource_metadata', sample)
        self.assertEqual(
            list(sorted(sample['resource_metadata'].iteritems())),
            [('dict_properties.key', 'value'),
             ('display_name', 'test-server'),
             ('not_ignored_list', "['returned']"),
             ('tag', 'self.sample'),
             ])
