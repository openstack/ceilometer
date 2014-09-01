#
# Copyright 2013 Intel Corp
#
# Authors: Lianhao Lu <lianhao.lu@intel.com>
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
"""Tests for ceilometer/hardware/inspector/snmp/inspector.py
"""
from oslo.utils import netutils
from oslotest import mockpatch

from ceilometer.hardware.inspector import snmp
from ceilometer.tests import base as test_base

ins = snmp.SNMPInspector


class FakeObjectName(object):
    def __init__(self, name):
        self.name = name

    def prettyPrint(self):
        return str(self.name)


def faux_getCmd_new(authData, transportTarget, *oids, **kwargs):
    varBinds = [(FakeObjectName(oid),
                 int(oid.split('.')[-1])) for oid in oids]
    return (None, None, 0, varBinds)


def faux_bulkCmd_new(authData, transportTarget, nonRepeaters, maxRepetitions,
                     *oids, **kwargs):
    varBindTable = [
        [(FakeObjectName(oid + ".%d" % i), i) for i in range(1, 3)]
        for oid in oids
    ]
    return (None, None, 0, varBindTable)


class TestSNMPInspector(test_base.BaseTestCase):
    mapping = {
        'test_exact': {
            'matching_type': snmp.EXACT,
            'metric_oid': ('1.3.6.1.4.1.2021.10.1.3.1', int),
            'metadata': {
                'meta': ('1.3.6.1.4.1.2021.10.1.3.8', int)
            },
            'post_op': '_fake_post_op',
        },
        'test_prefix': {
            'matching_type': snmp.PREFIX,
            'metric_oid': ('1.3.6.1.4.1.2021.9.1.8', int),
            'metadata': {
                'meta': ('1.3.6.1.4.1.2021.9.1.3', int)
            },
            'post_op': None,
        },
    }

    def setUp(self):
        super(TestSNMPInspector, self).setUp()
        self.inspector = snmp.SNMPInspector()
        self.host = netutils.urlsplit("snmp://localhost")
        self.inspector.MAPPING = self.mapping
        self.useFixture(mockpatch.PatchObject(
            self.inspector._cmdGen, 'getCmd', new=faux_getCmd_new))
        self.useFixture(mockpatch.PatchObject(
            self.inspector._cmdGen, 'bulkCmd', new=faux_bulkCmd_new))

    def test_snmp_error(self):
        def get_list(func, *args, **kwargs):
            return list(func(*args, **kwargs))

        def faux_parse(ret, is_bulk):
            return (True, 'forced error')

        self.useFixture(mockpatch.PatchObject(
            snmp, 'parse_snmp_return', new=faux_parse))

        self.assertRaises(snmp.SNMPException,
                          get_list,
                          self.inspector.inspect_generic,
                          self.host,
                          'test_exact',
                          {})

    def _fake_post_op(self, host, cache, meter_def,
                      value, metadata, extra, suffix):
        metadata.update(post_op_meta=4)
        extra.update(project_id=2)
        return value

    def test_inspect_generic_exact(self):
        self.inspector._fake_post_op = self._fake_post_op
        cache = {}
        ret = list(self.inspector.inspect_generic(self.host,
                                                  'test_exact',
                                                  cache))
        keys = cache[ins._CACHE_KEY_OID].keys()
        self.assertIn('1.3.6.1.4.1.2021.10.1.3.1', keys)
        self.assertIn('1.3.6.1.4.1.2021.10.1.3.8', keys)
        self.assertEqual(1, len(ret))
        self.assertEqual(1, ret[0][0])
        self.assertEqual(8, ret[0][1]['meta'])
        self.assertEqual(4, ret[0][1]['post_op_meta'])
        self.assertEqual(2, ret[0][2]['project_id'])

    def test_inspect_generic_prefix(self):
        cache = {}
        ret = list(self.inspector.inspect_generic(self.host,
                                                  'test_prefix',
                                                  cache))
        keys = cache[ins._CACHE_KEY_OID].keys()
        self.assertIn('1.3.6.1.4.1.2021.9.1.8' + '.1', keys)
        self.assertIn('1.3.6.1.4.1.2021.9.1.8' + '.2', keys)
        self.assertIn('1.3.6.1.4.1.2021.9.1.3' + '.1', keys)
        self.assertIn('1.3.6.1.4.1.2021.9.1.3' + '.2', keys)
        self.assertEqual(2, len(ret))
        self.assertIn(ret[0][0], (1, 2))
        self.assertEqual(ret[0][0], ret[0][1]['meta'])

    def test_post_op_net(self):
        self.useFixture(mockpatch.PatchObject(
            self.inspector._cmdGen, 'bulkCmd', new=faux_bulkCmd_new))
        cache = {}
        metadata = {}
        ret = self.inspector._post_op_net(self.host, cache, None,
                                          value=8,
                                          metadata=metadata,
                                          extra={},
                                          suffix=".2")
        self.assertEqual(8, ret)
        self.assertIn('ip', metadata)
        self.assertIn("2", metadata['ip'])
