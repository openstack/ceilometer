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


class TestSNMPInspector(Base, test_base.BaseTestCase):
    def setUp(self):
        super(TestSNMPInspector, self).setUp()
        self.inspector = snmp.SNMPInspector()
        self.host = network_utils.urlsplit("snmp://localhost")
        self.useFixture(mockpatch.PatchObject(
            self.inspector._cmdGen, 'getCmd', new=faux_getCmd))
        self.useFixture(mockpatch.PatchObject(
            self.inspector._cmdGen, 'nextCmd', new=faux_nextCmd))

    def test_get_security_name(self):
        self.assertEqual(self.inspector._get_security_name(self.host),
                         self.inspector._security_name)
        host2 = network_utils.urlsplit("snmp://foo:80?security_name=fake")
        self.assertEqual(self.inspector._get_security_name(host2),
                         'fake')

    def test_get_cmd_error(self):
        self.useFixture(mockpatch.PatchObject(
            self.inspector, '_memory_total_oid', new='failure'))

        def get_list(func, *args, **kwargs):
            return list(func(*args, **kwargs))

        self.assertRaises(snmp.SNMPException,
                          get_list,
                          self.inspector.inspect_memory,
                          self.host)
