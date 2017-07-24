#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright (c) 2013 OpenStack Foundation
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

from oslotest import base

from ceilometer import utils


class TestUtils(base.BaseTestCase):

    def test_datetime_to_decimal(self):
        expected = 1356093296.12
        utc_datetime = datetime.datetime.utcfromtimestamp(expected)
        actual = utils.dt_to_decimal(utc_datetime)
        self.assertAlmostEqual(expected, float(actual), places=5)

    def test_decimal_to_datetime(self):
        expected = 1356093296.12
        dexpected = decimal.Decimal(str(expected))  # Python 2.6 wants str()
        expected_datetime = datetime.datetime.utcfromtimestamp(expected)
        actual_datetime = utils.decimal_to_dt(dexpected)
        # Python 3 have rounding issue on this, so use float
        self.assertAlmostEqual(utils.dt_to_decimal(expected_datetime),
                               utils.dt_to_decimal(actual_datetime),
                               places=5)

    def test_recursive_keypairs(self):
        data = {'a': 'A', 'b': 'B',
                'nested': {'a': 'A', 'b': 'B'}}
        pairs = list(utils.recursive_keypairs(data))
        self.assertEqual([('a', 'A'), ('b', 'B'),
                          ('nested:a', 'A'), ('nested:b', 'B')],
                         pairs)

    def test_recursive_keypairs_with_separator(self):
        data = {'a': 'A',
                'b': 'B',
                'nested': {'a': 'A',
                           'b': 'B',
                           },
                }
        separator = '.'
        pairs = list(utils.recursive_keypairs(data, separator))
        self.assertEqual([('a', 'A'),
                          ('b', 'B'),
                          ('nested.a', 'A'),
                          ('nested.b', 'B')],
                         pairs)

    def test_recursive_keypairs_with_list_of_dict(self):
        small = 1
        big = 1 << 64
        expected = [('a', 'A'),
                    ('b', 'B'),
                    ('nested:list', [{small: 99, big: 42}])]
        data = {'a': 'A',
                'b': 'B',
                'nested': {'list': [{small: 99, big: 42}]}}
        pairs = list(utils.recursive_keypairs(data))
        self.assertEqual(len(expected), len(pairs))
        for k, v in pairs:
            # the keys 1 and 1<<64 cause a hash collision on 64bit platforms
            if k == 'nested:list':
                self.assertIn(v,
                              [[{small: 99, big: 42}],
                               [{big: 42, small: 99}]])
            else:
                self.assertIn((k, v), expected)

    def test_restore_nesting_unested(self):
        metadata = {'a': 'A', 'b': 'B'}
        unwound = utils.restore_nesting(metadata)
        self.assertIs(metadata, unwound)

    def test_restore_nesting(self):
        metadata = {'a': 'A', 'b': 'B',
                    'nested:a': 'A',
                    'nested:b': 'B',
                    'nested:twice:c': 'C',
                    'nested:twice:d': 'D',
                    'embedded:e': 'E'}
        unwound = utils.restore_nesting(metadata)
        expected = {'a': 'A', 'b': 'B',
                    'nested': {'a': 'A', 'b': 'B',
                               'twice': {'c': 'C', 'd': 'D'}},
                    'embedded': {'e': 'E'}}
        self.assertEqual(expected, unwound)
        self.assertIsNot(metadata, unwound)

    def test_restore_nesting_with_separator(self):
        metadata = {'a': 'A', 'b': 'B',
                    'nested.a': 'A',
                    'nested.b': 'B',
                    'nested.twice.c': 'C',
                    'nested.twice.d': 'D',
                    'embedded.e': 'E'}
        unwound = utils.restore_nesting(metadata, separator='.')
        expected = {'a': 'A', 'b': 'B',
                    'nested': {'a': 'A', 'b': 'B',
                               'twice': {'c': 'C', 'd': 'D'}},
                    'embedded': {'e': 'E'}}
        self.assertEqual(expected, unwound)
        self.assertIsNot(metadata, unwound)

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
        self.assertEqual([('a', 'A'),
                          ('b', 'B'),
                         ('nested.a', 'A'),
                         ('nested.b', 'B'),
                         ('nested2[0].c', 'A'),
                         ('nested2[1].c', 'B')],
                         sorted(pairs, key=lambda x: x[0]))

    def test_hash_of_set(self):
        x = ['a', 'b']
        y = ['a', 'b', 'a']
        z = ['a', 'c']
        self.assertEqual(utils.hash_of_set(x), utils.hash_of_set(y))
        self.assertNotEqual(utils.hash_of_set(x), utils.hash_of_set(z))
        self.assertNotEqual(utils.hash_of_set(y), utils.hash_of_set(z))

    def test_update_nested(self):
        original_dict = {'a': 'A',
                         'b': 'B',
                         'nested': {'a': 'A',
                                    'b': 'B',
                                    'nested': {'a': 'A',
                                               'b': 'B'
                                               }
                                    }
                         }
        updates = {'a': 'a',
                   'nested': {'a': 'nested.a',
                              'nested': {'a': 'nested.twice.a'}
                              }
                   }
        expected_dict = {'a': 'a',
                         'b': 'B',
                         'nested': {'a': 'nested.a',
                                    'b': 'B',
                                    'nested': {'a': 'nested.twice.a',
                                               'b': 'B'
                                               }
                                    }
                         }
        dict_to_update = utils.update_nested(original_dict, updates)
        self.assertEqual(dict_to_update, expected_dict)

    def test_uniq(self):
        class DriverA(object):
            source = 'class_A'
            func = 'func_A'
            param = 'param_A'

        class DriverB(object):
            source = 'class_A'
            func = 'func_A'
            param = 'param_B'

        class DriverC(object):
            source = 'class_A'
            func = 'func_C'
            param = 'param_C'

        driver_list = [DriverA(), DriverB(), DriverC()]

        uniq_driver_a = utils.uniq(driver_list, ['source'])
        self.assertEqual(len(uniq_driver_a), 1)

        uniq_driver_b = utils.uniq(driver_list, ['source', 'func'])
        self.assertEqual(len(uniq_driver_b), 2)

        uniq_driver_c = utils.uniq(driver_list, ['source', 'func', 'param'])
        self.assertEqual(len(uniq_driver_c), 3)
