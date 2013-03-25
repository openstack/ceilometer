# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance
#
# Author: Julien Danjou <julien@danjou.info>
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
import unittest

from ceilometer.storage import base


class BaseTest(unittest.TestCase):

    def test_iter_period(self):
        times = list(base.iter_period(
            datetime.datetime(2013, 01, 01, 12, 00),
            datetime.datetime(2013, 01, 01, 13, 00),
            60))
        self.assertEqual(len(times), 60)
        self.assertEqual(times[10],
                         (datetime.datetime(2013, 01, 01, 12, 10),
                          datetime.datetime(2013, 01, 01, 12, 11)))
        self.assertEqual(times[21],
                         (datetime.datetime(2013, 01, 01, 12, 21),
                          datetime.datetime(2013, 01, 01, 12, 22)))

    def test_iter_period_bis(self):
        times = list(base.iter_period(
            datetime.datetime(2013, 01, 02, 13, 00),
            datetime.datetime(2013, 01, 02, 14, 00),
            55))
        self.assertEqual(len(times), math.ceil(3600 / 55.0))
        self.assertEqual(times[10],
                         (datetime.datetime(2013, 01, 02, 13, 9, 10),
                          datetime.datetime(2013, 01, 02, 13, 10, 5)))
        self.assertEqual(times[21],
                         (datetime.datetime(2013, 01, 02, 13, 19, 15),
                          datetime.datetime(2013, 01, 02, 13, 20, 10)))
