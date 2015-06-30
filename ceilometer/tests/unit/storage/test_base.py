# Copyright 2013 eNovance
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
import datetime
import math

from oslotest import base as testbase

from ceilometer.storage import base


class BaseTest(testbase.BaseTestCase):

    def test_iter_period(self):
        times = list(base.iter_period(
            datetime.datetime(2013, 1, 1, 12, 0),
            datetime.datetime(2013, 1, 1, 13, 0),
            60))
        self.assertEqual(60, len(times))
        self.assertEqual((datetime.datetime(2013, 1, 1, 12, 10),
                          datetime.datetime(2013, 1, 1, 12, 11)), times[10])
        self.assertEqual((datetime.datetime(2013, 1, 1, 12, 21),
                          datetime.datetime(2013, 1, 1, 12, 22)), times[21])

    def test_iter_period_bis(self):
        times = list(base.iter_period(
            datetime.datetime(2013, 1, 2, 13, 0),
            datetime.datetime(2013, 1, 2, 14, 0),
            55))
        self.assertEqual(math.ceil(3600 / 55.0), len(times))
        self.assertEqual((datetime.datetime(2013, 1, 2, 13, 9, 10),
                          datetime.datetime(2013, 1, 2, 13, 10, 5)),
                         times[10])
        self.assertEqual((datetime.datetime(2013, 1, 2, 13, 19, 15),
                          datetime.datetime(2013, 1, 2, 13, 20, 10)),
                         times[21])

    def test_handle_sort_key(self):
        sort_keys_meter = base._handle_sort_key('meter', 'foo')
        self.assertEqual(['foo', 'user_id', 'project_id'], sort_keys_meter)

        sort_keys_resource = base._handle_sort_key('resource', 'project_id')
        self.assertEqual(['project_id', 'user_id', 'timestamp'],
                         sort_keys_resource)
