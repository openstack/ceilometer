#
# Copyright 2016 Mirantis Inc.
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
import mock
from oslotest import base

from ceilometer.event import trait_plugins


class TestTimedeltaPlugin(base.BaseTestCase):

    def setUp(self):
        super(TestTimedeltaPlugin, self).setUp()
        self.plugin = trait_plugins.TimedeltaPlugin()

    def test_timedelta_transformation(self):
        match_list = [('test.timestamp1', '2016-03-02T15:04:32'),
                      ('test.timestamp2', '2016-03-02T16:04:32')]
        value = self.plugin.trait_value(match_list)
        self.assertEqual(3600, value)

    def test_timedelta_missing_field(self):
        match_list = [('test.timestamp1', '2016-03-02T15:04:32')]
        with mock.patch('%s.LOG' % self.plugin.trait_value.__module__) as log:
            self.assertIsNone(self.plugin.trait_value(match_list))
            log.warning.assert_called_once_with(
                'Timedelta plugin is required two timestamp fields to create '
                'timedelta value.')

    def test_timedelta_exceed_field(self):
        match_list = [('test.timestamp1', '2016-03-02T15:04:32'),
                      ('test.timestamp2', '2016-03-02T16:04:32'),
                      ('test.timestamp3', '2016-03-02T16:10:32')]
        with mock.patch('%s.LOG' % self.plugin.trait_value.__module__) as log:
            self.assertIsNone(self.plugin.trait_value(match_list))
            log.warning.assert_called_once_with(
                'Timedelta plugin is required two timestamp fields to create '
                'timedelta value.')

    def test_timedelta_invalid_timestamp(self):
        match_list = [('test.timestamp1', '2016-03-02T15:04:32'),
                      ('test.timestamp2', '2016-03-02T15:004:32')]
        with mock.patch('%s.LOG' % self.plugin.trait_value.__module__) as log:
            self.assertIsNone(self.plugin.trait_value(match_list))
            msg = log.warning._mock_call_args[0][0]
            self.assertTrue(msg.startswith('Failed to parse date from set '
                                           'fields, both fields ')
                            )

    def test_timedelta_reverse_timestamp_order(self):
        match_list = [('test.timestamp1', '2016-03-02T15:15:32'),
                      ('test.timestamp2', '2016-03-02T15:10:32')]
        value = self.plugin.trait_value(match_list)
        self.assertEqual(300, value)

    def test_timedelta_precise_difference(self):
        match_list = [('test.timestamp1', '2016-03-02T15:10:32.786893'),
                      ('test.timestamp2', '2016-03-02T15:10:32.786899')]
        value = self.plugin.trait_value(match_list)
        self.assertEqual(0.000006, value)
