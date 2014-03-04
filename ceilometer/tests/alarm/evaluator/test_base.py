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
import datetime
import mock
import pytz

from ceilometer.alarm import evaluator
from ceilometer.openstack.common import test
from ceilometer.openstack.common import timeutils


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

    def test_base_time_constraints(self):
        alarm = mock.MagicMock()
        alarm.time_constraints = [
            {'name': 'test',
             'description': 'test',
             'start': '0 11 * * *',  # daily at 11:00
             'duration': 10800,  # 3 hours
             'timezone': ''},
            {'name': 'test2',
             'description': 'test',
             'start': '0 23 * * *',  # daily at 23:00
             'duration': 10800,  # 3 hours
             'timezone': ''},
        ]
        cls = evaluator.Evaluator
        timeutils.set_time_override(datetime.datetime(2014, 1, 1, 12, 0, 0))
        self.assertTrue(cls.within_time_constraint(alarm))

        timeutils.set_time_override(datetime.datetime(2014, 1, 2, 1, 0, 0))
        self.assertTrue(cls.within_time_constraint(alarm))

        timeutils.set_time_override(datetime.datetime(2014, 1, 2, 5, 0, 0))
        self.assertFalse(cls.within_time_constraint(alarm))

    def test_base_time_constraints_complex(self):
        alarm = mock.MagicMock()
        alarm.time_constraints = [
            {'name': 'test',
             'description': 'test',
             # Every consecutive 2 minutes (from the 3rd to the 57th) past
             # every consecutive 2 hours (between 3:00 and 12:59) on every day.
             'start': '3-57/2 3-12/2 * * *',
             'duration': 30,
             'timezone': ''}
        ]
        cls = evaluator.Evaluator

        # test minutes inside
        timeutils.set_time_override(datetime.datetime(2014, 1, 5, 3, 3, 0))
        self.assertTrue(cls.within_time_constraint(alarm))
        timeutils.set_time_override(datetime.datetime(2014, 1, 5, 3, 31, 0))
        self.assertTrue(cls.within_time_constraint(alarm))
        timeutils.set_time_override(datetime.datetime(2014, 1, 5, 3, 57, 0))
        self.assertTrue(cls.within_time_constraint(alarm))

        # test minutes outside
        timeutils.set_time_override(datetime.datetime(2014, 1, 5, 3, 2, 0))
        self.assertFalse(cls.within_time_constraint(alarm))
        timeutils.set_time_override(datetime.datetime(2014, 1, 5, 3, 4, 0))
        self.assertFalse(cls.within_time_constraint(alarm))
        timeutils.set_time_override(datetime.datetime(2014, 1, 5, 3, 58, 0))
        self.assertFalse(cls.within_time_constraint(alarm))

        # test hours inside
        timeutils.set_time_override(datetime.datetime(2014, 1, 5, 3, 31, 0))
        self.assertTrue(cls.within_time_constraint(alarm))
        timeutils.set_time_override(datetime.datetime(2014, 1, 5, 5, 31, 0))
        self.assertTrue(cls.within_time_constraint(alarm))
        timeutils.set_time_override(datetime.datetime(2014, 1, 5, 11, 31, 0))
        self.assertTrue(cls.within_time_constraint(alarm))

        # test hours outside
        timeutils.set_time_override(datetime.datetime(2014, 1, 5, 1, 31, 0))
        self.assertFalse(cls.within_time_constraint(alarm))
        timeutils.set_time_override(datetime.datetime(2014, 1, 5, 4, 31, 0))
        self.assertFalse(cls.within_time_constraint(alarm))
        timeutils.set_time_override(datetime.datetime(2014, 1, 5, 12, 31, 0))
        self.assertFalse(cls.within_time_constraint(alarm))

    def test_base_time_constraints_timezone(self):
        alarm = mock.MagicMock()
        alarm.time_constraints = [
            {'name': 'test',
             'description': 'test',
             'start': '0 11 * * *',  # daily at 11:00
             'duration': 10800,  # 3 hours
             'timezone': 'Europe/Ljubljana'}
        ]
        cls = evaluator.Evaluator
        dt_eu = datetime.datetime(2014, 1, 1, 12, 0, 0,
                                  tzinfo=pytz.timezone('Europe/Ljubljana'))
        dt_us = datetime.datetime(2014, 1, 1, 12, 0, 0,
                                  tzinfo=pytz.timezone('US/Eastern'))
        timeutils.set_time_override(dt_eu.astimezone(pytz.UTC))
        self.assertTrue(cls.within_time_constraint(alarm))

        timeutils.set_time_override(dt_us.astimezone(pytz.UTC))
        self.assertFalse(cls.within_time_constraint(alarm))
