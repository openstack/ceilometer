# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Steven Berler <steven.berler@dreamhost.com>
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
"""Test the _get_query_timestamps helper function.
"""

import unittest
import datetime

from ceilometer.api.controllers import v2 as api


class DateRangeTest(unittest.TestCase):

    def test_get_query_timestamps_none_specified(self):
        result = api.DateRange().to_dict()
        expected = {'start_timestamp': None,
                    'end_timestamp': None,
                    'query_start': None,
                    'query_end': None,
                    'search_offset': 0,
                    }

        assert result == expected

    def test_get_query_timestamps_start(self):
        d = datetime.datetime(2012, 9, 20, 12, 13, 14)
        result = api.DateRange(start=d).to_dict()
        expected = {
            'start_timestamp': datetime.datetime(2012, 9, 20, 12, 13, 14),
            'end_timestamp': None,
            'query_start': datetime.datetime(2012, 9, 20, 12, 13, 14),
            'query_end': None,
            'search_offset': 0,
            }

        assert result == expected

    def test_get_query_timestamps_end(self):
        d = datetime.datetime(2012, 9, 20, 12, 13, 14)
        result = api.DateRange(end=d).to_dict()
        expected = {
            'end_timestamp': datetime.datetime(2012, 9, 20, 12, 13, 14),
            'start_timestamp': None,
            'query_end': datetime.datetime(2012, 9, 20, 12, 13, 14),
            'query_start': None,
            'search_offset': 0,
            }

        assert result == expected

    def test_get_query_timestamps_with_offset(self):
        result = api.DateRange(
            end=datetime.datetime(2012, 9, 20, 13, 24, 25),
            start=datetime.datetime(2012, 9, 20, 12, 13, 14),
            search_offset=20,
            ).to_dict()
        expected = {
            'query_end': datetime.datetime(2012, 9, 20, 13, 44, 25),
            'query_start': datetime.datetime(2012, 9, 20, 11, 53, 14),
            'end_timestamp': datetime.datetime(2012, 9, 20, 13, 24, 25),
            'start_timestamp': datetime.datetime(2012, 9, 20, 12, 13, 14),
            'search_offset': 20,
            }

        assert result == expected
