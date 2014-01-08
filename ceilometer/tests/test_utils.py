# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
# Copyright (c) 2013 OpenStack Foundation
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
# All Rights Reserved.
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
"""Tests for ceilometer/utils.py
"""
import datetime
import decimal

from ceilometer.openstack.common import test
from ceilometer import utils


class TestUtils(test.BaseTestCase):

    def test_datetime_to_decimal(self):
        expected = 1356093296.12
        utc_datetime = datetime.datetime.utcfromtimestamp(expected)
        actual = utils.dt_to_decimal(utc_datetime)
        self.assertEqual(float(actual), expected)

    def test_decimal_to_datetime(self):
        expected = 1356093296.12
        dexpected = decimal.Decimal(str(expected))  # Python 2.6 wants str()
        expected_datetime = datetime.datetime.utcfromtimestamp(expected)
        actual_datetime = utils.decimal_to_dt(dexpected)
        self.assertEqual(actual_datetime, expected_datetime)

    def test_recursive_keypairs(self):
        data = {'a': 'A',
                'b': 'B',
                'nested': {'a': 'A',
                           'b': 'B',
                           },
                }
        pairs = list(utils.recursive_keypairs(data))
        self.assertEqual(pairs, [('a', 'A'),
                                 ('b', 'B'),
                                 ('nested:a', 'A'),
                                 ('nested:b', 'B')])

    def test_recursive_keypairs_with_separator(self):
        data = {'a': 'A',
                'b': 'B',
                'nested': {'a': 'A',
                           'b': 'B',
                           },
                }
        separator = '.'
        pairs = list(utils.recursive_keypairs(data, separator))
        self.assertEqual(pairs, [('a', 'A'),
                                 ('b', 'B'),
                                 ('nested.a', 'A'),
                                 ('nested.b', 'B')])

    def test_recursive_keypairs_with_list_of_dict(self):
        small = 1
        big = 1 << 64
        expected = [('a', 'A'),
                    ('b', 'B'),
                    ('nested:list', ['{%d: 99, %dL: 42}' % (small, big)])]
        # the keys 1 and 1<<64 cause a hash collision on 64bit platforms
        for nested in [{small: 99, big: 42}, {big: 42, small: 99}]:
            data = {'a': 'A',
                    'b': 'B',
                    'nested': {'list': [nested]}}
            pairs = list(utils.recursive_keypairs(data))
            self.assertEqual(pairs, expected)

    def test_decimal_to_dt_with_none_parameter(self):
        self.assertIsNone(utils.decimal_to_dt(None))

    def test_dict_to_kv(self):
        data = {'a': 'A',
                'b': 'B',
                'nested': {'a': 'A',
                           'b': 'B',
                           },
                'nested2': [{'c': 'A'}, {'c': 'B'}]
                }
        pairs = list(utils.dict_to_keyval(data))
        self.assertEqual(pairs, [('a', 'A'),
                                 ('b', 'B'),
                                 ('nested2[0].c', 'A'),
                                 ('nested2[1].c', 'B'),
                                 ('nested.a', 'A'),
                                 ('nested.b', 'B')])
