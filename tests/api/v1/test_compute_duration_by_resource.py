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

from ceilometer.openstack.common import timeutils

from ceilometer.tests import api as tests_api

LOG = logging.getLogger(__name__)


class TestComputeDurationByResource(tests_api.TestBase):

    def setUp(self):
        super(TestComputeDurationByResource, self).setUp()

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

    def _set_interval(self, start, end):
        def get_interval(event_filter):
            assert event_filter.start
            assert event_filter.end
            return (start, end)
        self.stubs.Set(self.conn, 'get_event_interval', get_interval)

    def _invoke_api(self):
        return self.get(
            '/resources/resource-id/meters/instance:m1.tiny/duration',
            start_timestamp=self.start.isoformat(),
            end_timestamp=self.end.isoformat(),
            search_offset=10,  # this value doesn't matter, db call is mocked
        )

    def test_before_range(self):
        self._set_interval(self.early1, self.early2)
        data = self._invoke_api()
        assert data['start_timestamp'] is None
        assert data['end_timestamp'] is None
        assert data['duration'] is None

    def _assert_times_match(self, actual, expected):
        actual = timeutils.parse_isotime(actual).replace(tzinfo=None)
        assert actual == expected

    def test_overlap_range_start(self):
        self._set_interval(self.early1, self.middle1)
        data = self._invoke_api()
        self._assert_times_match(data['start_timestamp'], self.start)
        self._assert_times_match(data['end_timestamp'], self.middle1)
        assert data['duration'] == 8 * 60

    def test_within_range(self):
        self._set_interval(self.middle1, self.middle2)
        data = self._invoke_api()
        self._assert_times_match(data['start_timestamp'], self.middle1)
        self._assert_times_match(data['end_timestamp'], self.middle2)
        assert data['duration'] == 10 * 60

    def test_within_range_zero_duration(self):
        self._set_interval(self.middle1, self.middle1)
        data = self._invoke_api()
        self._assert_times_match(data['start_timestamp'], self.middle1)
        self._assert_times_match(data['end_timestamp'], self.middle1)
        assert data['duration'] == 0

    def test_overlap_range_end(self):
        self._set_interval(self.middle2, self.late1)
        data = self._invoke_api()
        self._assert_times_match(data['start_timestamp'], self.middle2)
        self._assert_times_match(data['end_timestamp'], self.end)
        assert data['duration'] == (6 * 60) - 1

    def test_after_range(self):
        self._set_interval(self.late1, self.late2)
        data = self._invoke_api()
        assert data['start_timestamp'] is None
        assert data['end_timestamp'] is None
        assert data['duration'] is None

    def test_without_end_timestamp(self):
        def get_interval(event_filter):
            return (self.late1, self.late2)
        self.stubs.Set(self.conn, 'get_event_interval', get_interval)
        data = self.get(
            '/resources/resource-id/meters/instance:m1.tiny/duration',
            start_timestamp=self.late1.isoformat(),
            search_offset=10,  # this value doesn't matter, db call is mocked
        )
        self._assert_times_match(data['start_timestamp'], self.late1)
        self._assert_times_match(data['end_timestamp'], self.late2)

    def test_without_start_timestamp(self):
        def get_interval(event_filter):
            return (self.early1, self.early2)
        self.stubs.Set(self.conn, 'get_event_interval', get_interval)
        data = self.get(
            '/resources/resource-id/meters/instance:m1.tiny/duration',
            end_timestamp=self.early2.isoformat(),
            search_offset=10,  # this value doesn't matter, db call is mocked
        )
        self._assert_times_match(data['start_timestamp'], self.early1)
        self._assert_times_match(data['end_timestamp'], self.early2)
