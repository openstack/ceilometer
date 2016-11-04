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
"""Tests for ceilometer/publisher/utils.py
"""
from oslo_serialization import jsonutils
from oslotest import base

from ceilometer.publisher import utils


class TestSignature(base.BaseTestCase):
    def test_compute_signature_change_key(self):
        sig1 = utils.compute_signature({'a': 'A', 'b': 'B'},
                                       'not-so-secret')
        sig2 = utils.compute_signature({'A': 'A', 'b': 'B'},
                                       'not-so-secret')
        self.assertNotEqual(sig1, sig2)

    def test_compute_signature_change_value(self):
        sig1 = utils.compute_signature({'a': 'A', 'b': 'B'},
                                       'not-so-secret')
        sig2 = utils.compute_signature({'a': 'a', 'b': 'B'},
                                       'not-so-secret')
        self.assertNotEqual(sig1, sig2)

    def test_compute_signature_same(self):
        sig1 = utils.compute_signature({'a': 'A', 'b': 'B'},
                                       'not-so-secret')
        sig2 = utils.compute_signature({'a': 'A', 'b': 'B'},
                                       'not-so-secret')
        self.assertEqual(sig1, sig2)

    def test_compute_signature_signed(self):
        data = {'a': 'A', 'b': 'B'}
        sig1 = utils.compute_signature(data, 'not-so-secret')
        data['message_signature'] = sig1
        sig2 = utils.compute_signature(data, 'not-so-secret')
        self.assertEqual(sig1, sig2)

    def test_compute_signature_use_configured_secret(self):
        data = {'a': 'A', 'b': 'B'}
        sig1 = utils.compute_signature(data, 'not-so-secret')
        sig2 = utils.compute_signature(data, 'different-value')
        self.assertNotEqual(sig1, sig2)

    def test_verify_signature_signed(self):
        data = {'a': 'A', 'b': 'B'}
        sig1 = utils.compute_signature(data, 'not-so-secret')
        data['message_signature'] = sig1
        self.assertTrue(utils.verify_signature(data, 'not-so-secret'))

    def test_verify_signature_unsigned(self):
        data = {'a': 'A', 'b': 'B'}
        self.assertFalse(utils.verify_signature(data, 'not-so-secret'))

    def test_verify_signature_incorrect(self):
        data = {'a': 'A', 'b': 'B',
                'message_signature': 'Not the same'}
        self.assertFalse(utils.verify_signature(data, 'not-so-secret'))

    def test_verify_signature_invalid_encoding(self):
        data = {'a': 'A', 'b': 'B',
                'message_signature': ''}
        self.assertFalse(utils.verify_signature(data, 'not-so-secret'))

    def test_verify_signature_unicode(self):
        data = {'a': 'A', 'b': 'B',
                'message_signature': u''}
        self.assertFalse(utils.verify_signature(data, 'not-so-secret'))

    def test_verify_signature_nested(self):
        data = {'a': 'A',
                'b': 'B',
                'nested': {'a': 'A',
                           'b': 'B',
                           },
                }
        data['message_signature'] = utils.compute_signature(
            data,
            'not-so-secret')
        self.assertTrue(utils.verify_signature(data, 'not-so-secret'))

    def test_verify_signature_nested_json(self):
        data = {'a': 'A',
                'b': 'B',
                'nested': {'a': 'A',
                           'b': 'B',
                           'c': ('c',),
                           'd': ['d']
                           },
                }
        data['message_signature'] = utils.compute_signature(
            data,
            'not-so-secret')
        jsondata = jsonutils.loads(jsonutils.dumps(data))
        self.assertTrue(utils.verify_signature(jsondata, 'not-so-secret'))

    def test_verify_unicode_symbols(self):
        data = {u'a\xe9\u0437': 'A',
                'b': u'B\xe9\u0437'
                }
        data['message_signature'] = utils.compute_signature(
            data,
            'not-so-secret')
        jsondata = jsonutils.loads(jsonutils.dumps(data))
        self.assertTrue(utils.verify_signature(jsondata, 'not-so-secret'))

    def test_verify_no_secret(self):
        data = {'a': 'A', 'b': 'B'}
        self.assertTrue(utils.verify_signature(data, ''))
