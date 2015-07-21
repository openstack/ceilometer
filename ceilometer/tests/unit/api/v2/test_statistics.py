#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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
"""Test statistics objects."""

import datetime

from oslotest import base

from ceilometer.api.controllers.v2 import meters


class TestStatisticsDuration(base.BaseTestCase):

    def setUp(self):
        super(TestStatisticsDuration, self).setUp()

        # Create events relative to the range and pretend
        # that the intervening events exist.

        self.early1 = datetime.datetime(2012, 8, 27, 7, 0)
        self.early2 = datetime.datetime(2012, 8, 27, 17, 0)

        self.start = datetime.datetime(2012, 8, 28, 0, 0)

        self.middle1 = datetime.datetime(2012, 8, 28, 8, 0)
        self.middle2 = datetime.datetime(2012, 8, 28, 18, 0)

        self.end = datetime.datetime(2012, 8, 28, 23, 59)

        self.late1 = datetime.datetime(2012, 8, 29, 9, 0)
        self.late2 = datetime.datetime(2012, 8, 29, 19, 0)

    def test_nulls(self):
        s = meters.Statistics(duration_start=None,
                              duration_end=None,
                              start_timestamp=None,
                              end_timestamp=None)
        self.assertIsNone(s.duration_start)
        self.assertIsNone(s.duration_end)
        self.assertIsNone(s.duration)

    def test_overlap_range_start(self):
        s = meters.Statistics(duration_start=self.early1,
                              duration_end=self.middle1,
                              start_timestamp=self.start,
                              end_timestamp=self.end)
        self.assertEqual(self.start, s.duration_start)
        self.assertEqual(self.middle1, s.duration_end)
        self.assertEqual(8 * 60 * 60, s.duration)

    def test_within_range(self):
        s = meters.Statistics(duration_start=self.middle1,
                              duration_end=self.middle2,
                              start_timestamp=self.start,
                              end_timestamp=self.end)
        self.assertEqual(self.middle1, s.duration_start)
        self.assertEqual(self.middle2, s.duration_end)
        self.assertEqual(10 * 60 * 60, s.duration)

    def test_within_range_zero_duration(self):
        s = meters.Statistics(duration_start=self.middle1,
                              duration_end=self.middle1,
                              start_timestamp=self.start,
                              end_timestamp=self.end)
        self.assertEqual(self.middle1, s.duration_start)
        self.assertEqual(self.middle1, s.duration_end)
        self.assertEqual(0, s.duration)

    def test_overlap_range_end(self):
        s = meters.Statistics(duration_start=self.middle2,
                              duration_end=self.late1,
                              start_timestamp=self.start,
                              end_timestamp=self.end)
        self.assertEqual(self.middle2, s.duration_start)
        self.assertEqual(self.end, s.duration_end)
        self.assertEqual(((6 * 60) - 1) * 60, s.duration)

    def test_after_range(self):
        s = meters.Statistics(duration_start=self.late1,
                              duration_end=self.late2,
                              start_timestamp=self.start,
                              end_timestamp=self.end)
        self.assertIsNone(s.duration_start)
        self.assertIsNone(s.duration_end)
        self.assertIsNone(s.duration)

    def test_without_timestamp(self):
        s = meters.Statistics(duration_start=self.late1,
                              duration_end=self.late2,
                              start_timestamp=None,
                              end_timestamp=None)
        self.assertEqual(self.late1, s.duration_start)
        self.assertEqual(self.late2, s.duration_end)
