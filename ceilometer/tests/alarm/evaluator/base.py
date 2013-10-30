# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance <licensing@enovance.com>
#
# Author: Mehdi Abaakouk <mehdi.abaakouk@enovance.com>
#         Eoghan Glynn <eglynn@redhat.com>
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
"""Base class for tests in ceilometer/alarm/evaluator/
"""
import mock

from ceilometer.openstack.common import test
from ceilometer.openstack.common import timeutils


class TestEvaluatorBase(test.BaseTestCase):
    def setUp(self):
        super(TestEvaluatorBase, self).setUp()
        self.api_client = mock.Mock()
        self.notifier = mock.MagicMock()
        self.evaluator = self.EVALUATOR(self.notifier)
        self.prepare_alarms()

    def tearDown(self):
        super(TestEvaluatorBase, self).tearDown()
        timeutils.utcnow.override_time = None

    @staticmethod
    def prepare_alarms(self):
        self.alarms = []

    def _evaluate_all_alarms(self):
        for alarm in self.alarms:
            self.evaluator.evaluate(alarm)

    def _set_all_alarms(self, state):
        for alarm in self.alarms:
            alarm.state = state

    def _assert_all_alarms(self, state):
        for alarm in self.alarms:
            self.assertEqual(alarm.state, state)
