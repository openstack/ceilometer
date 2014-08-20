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

from ceilometer.hardware.inspector import snmp
from ceilometer.openstack.common.fixture import mockpatch
from ceilometer.openstack.common import network_utils
from ceilometer.tests import base as test_base
from ceilometer.tests.hardware.inspector import base

Base = base.InspectorBaseTest


class FakeMac(object):
    def __init__(self):
        self.val = "0x%s" % Base.network[0][0].mac

    def prettyPrint(self):
        return str(self.val)

ins = snmp.SNMPInspector
GETCMD_MAP = {
    ins._cpu_1_min_load_oid: (None,
                              None,
                              0,
                              [('',
                                Base.cpu[0].cpu_1_min,
                                )],
                              ),
    ins._cpu_5_min_load_oid: (None,
                              None,
                              0,
                              [('',
                                Base.cpu[0].cpu_5_min,
                                )],
                              ),
    ins._cpu_15_min_load_oid: (None,
                               None,
                               0,
                               [('',
                                 Base.cpu[0].cpu_15_min,
                                 )],
                               ),
    ins._memory_total_oid: (None,
                            None,
                            0,
                            [('',
                              Base.memory[0].total,
                              )],
                            ),
    ins._memory_used_oid: (None,
                           None,
                           0,
                           [('',
                             Base.memory[0].used,
                             )],
                           ),
    ins._disk_path_oid + '.1': (None,
                                None,
                                0,
                                [('',
                                  Base.diskspace[0][0].path,
                                  )],
                                ),
    ins._disk_device_oid + '.1': (None,
                                  None,
                                  0,
                                  [('',
                                    Base.diskspace[0][0].device,
                                    )],
                                  ),
    ins._disk_size_oid + '.1': (None,
                                None,
                                0,
                                [('',
                                  Base.diskspace[0][1].size,
                                  )],
                                ),
    ins._disk_used_oid + '.1': (None,
                                None,
                                0,
                                [('',
                                  Base.diskspace[0][1].used,
                                  )],
                                ),
    ins._disk_path_oid + '.2': (None,
                                None,
                                0,
                                [('',
                                  Base.diskspace[1][0].path,
                                  )],
                                ),
    ins._disk_device_oid + '.2': (None,
                                  None,
                                  0,
                                  [('',
                                    Base.diskspace[1][0].device,
                                    )],
                                  ),
    ins._disk_size_oid + '.2': (None,
                                None,
                                0,
                                [('',
                                  Base.diskspace[1][1].size,
                                  )],
                                ),
    ins._disk_used_oid + '.2': (None,
                                None,
                                0,
                                [('',
                                  Base.diskspace[1][1].used,
                                  )],
                                ),
    ins._interface_name_oid + '.1': (None,
                                     None,
                                     0,
                                     [('',
                                       Base.network[0][0].name,
                                       )],
                                     ),
    ins._interface_mac_oid + '.1': (None,
                                    None,
                                    0,
                                    [('',
                                      FakeMac(),
                                      )],
                                    ),
    ins._interface_speed_oid + '.1': (None,
                                      None,
                                      0,
                                      [('',
                                        Base.network[0][0].speed * 8,
                                        )],
                                      ),
    ins._interface_received_oid + '.1': (None,
                                         None,
                                         0,
                                         [('',
                                           Base.network[0][1].rx_bytes,
                                           )],
                                         ),
    ins._interface_transmitted_oid + '.1': (None,
                                            None,
                                            0,
                                            [('',
                                              Base.network[0][1].tx_bytes,
                                              )],
                                            ),
    ins._interface_error_oid + '.1': (None,
                                      None,
                                      0,
                                      [('',
                                        Base.network[0][1].error,
                                        )],
                                      ),
}

NEXTCMD_MAP = {
    ins._disk_index_oid: (None,
                          None,
                          0,
                          [[('1.3.6.1.4.1.2021.9.1.1.1', 1)],
                           [('1.3.6.1.4.1.2021.9.1.1.2', 2)]]),
    ins._interface_index_oid: (None,
                               None,
                               0,
                               [[('1.3.6.1.2.1.2.2.1.1.1', 1)],
                                ]),
    ins._interface_ip_oid: (None,
                            None,
                            0,
                            [[('1.3.6.1.2.1.4.20.1.2.10.0.0.1',
                               1)],
                             ]),
}


class FakeObjectName(object):
    def __init__(self, name):
        self.name = name

    def prettyPrint(self):
        return str(self.name)


def faux_getCmd(authData, transportTarget, oid):
    try:
        return GETCMD_MAP[oid]
    except KeyError:
        return ("faux_getCmd Error", None, 0, [])


def faux_nextCmd(authData, transportTarget, oid):
    try:
        return NEXTCMD_MAP[oid]
    except KeyError:
        return ("faux_nextCmd Error", None, 0, [])


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


class TestSNMPInspector(Base, test_base.BaseTestCase):
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
        self.host = network_utils.urlsplit("snmp://localhost")
        self.inspector.MAPPING = self.mapping
        self.useFixture(mockpatch.PatchObject(
            self.inspector._cmdGen, 'getCmd', new=faux_getCmd))
        self.useFixture(mockpatch.PatchObject(
            self.inspector._cmdGen, 'nextCmd', new=faux_nextCmd))

    def test_get_cmd_error(self):
        self.useFixture(mockpatch.PatchObject(
            self.inspector, '_memory_total_oid', new='failure'))

        def get_list(func, *args, **kwargs):
            return list(func(*args, **kwargs))

        self.assertRaises(snmp.SNMPException,
                          get_list,
                          self.inspector.inspect_memory,
                          self.host)

    def _fake_post_op(self, host, cache, meter_def,
                      value, metadata, extra, suffix):
        metadata.update(post_op_meta=4)
        extra.update(project_id=2)
        return value

    def test_inspect_generic_exact(self):
        self.useFixture(mockpatch.PatchObject(
            self.inspector._cmdGen, 'getCmd', new=faux_getCmd_new))
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
        self.useFixture(mockpatch.PatchObject(
            self.inspector._cmdGen, 'bulkCmd', new=faux_bulkCmd_new))
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
