#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
#
# Author: Guillaume Pernot <gpernot@praksys.org>
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

from ceilometer.objectstore import swift
from ceilometer.tests import base

ACCOUNTS = [('tenant-000', {'x-account-object-count': 12,
                            'x-account-bytes-used': 321321321,
                            'x-account-container-count': 7,
                            }),
            ('tenant-001', {'x-account-object-count': 34,
                            'x-account-bytes-used': 9898989898,
                            'x-account-container-count': 17,
                            })]


class TestSwiftPollster(base.TestCase):

    @staticmethod
    def fake_iter_accounts(_dummy):
        for i in ACCOUNTS:
            yield i

    def setUp(self):
        super(TestSwiftPollster, self).setUp()
        self.pollster = swift.SwiftPollster()
        self.stubs.Set(swift.SwiftPollster, 'iter_accounts',
                       self.fake_iter_accounts)

    def test_objectstore_metering(self):
        counters = list(self.pollster.get_counters(None, None))
        self.assertEqual(len(counters), 6)
