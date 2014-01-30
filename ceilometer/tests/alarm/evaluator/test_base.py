# -*- encoding: utf-8 -*-
#
# Copyright © 2013 IBM Corp
#
# Author: Tong Li <litong01@us.ibm.com>
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
"""class for tests in ceilometer/alarm/evaluator/__init__.py
"""
import mock

from ceilometer.alarm import evaluator
from ceilometer.openstack.common import test


class TestEvaluatorBaseClass(test.BaseTestCase):
    def setUp(self):
        super(TestEvaluatorBaseClass, self).setUp()
        self.called = False

    def _notify(self, alarm, previous, reason, details):
        self.called = True
        raise Exception('Boom!')

    def test_base_refresh(self):
        notifier = mock.MagicMock()
        notifier.notify = self._notify

        class EvaluatorSub(evaluator.Evaluator):
            def evaluate(self, alarm):
                pass

        ev = EvaluatorSub(notifier)
        ev.api_client = mock.MagicMock()
        ev._refresh(mock.MagicMock(), mock.MagicMock(),
                    mock.MagicMock(), mock.MagicMock())
        self.assertTrue(self.called)
