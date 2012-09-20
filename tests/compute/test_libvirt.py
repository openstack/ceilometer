#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
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
"""Tests for manager.
"""

import unittest

try:
    import libvirt as ignored_libvirt
except ImportError:
    libvirt_missing = True
else:
    libvirt_missing = False

import mock

from nova import flags

from ceilometer.compute import libvirt
from ceilometer.compute import manager
from ceilometer.tests import base as test_base
from ceilometer.tests import skip

import mox
import re


class TestDiskIOPollster(unittest.TestCase):

    def setUp(self):
        self.manager = manager.AgentManager()
        self.pollster = libvirt.DiskIOPollster()
        super(TestDiskIOPollster, self).setUp()
        self.instance = mock.MagicMock()
        self.instance.name = 'instance-00000001'
        self.instance.id = 1
        flags.FLAGS.compute_driver = 'libvirt.LibvirtDriver'
        flags.FLAGS.connection_type = 'libvirt'

    @skip.skip_if(libvirt_missing, 'Test requires libvirt')
    def test_fetch_diskio(self):
        list(self.pollster.get_counters(self.manager, self.instance))
        #assert counters
        # FIXME(dhellmann): The CI environment doesn't produce
        # a response when the fake driver asks for the disks, so
        # we do not get any counters in response.

    @skip.skip_if(libvirt_missing, 'Test requires libvirt')
    def test_fetch_diskio_not_libvirt(self):
        flags.FLAGS.compute_driver = 'fake.FakeDriver'
        flags.FLAGS.connection_type = 'fake'
        counters = list(self.pollster.get_counters(self.manager,
                                                   self.instance))
        assert not counters

    @skip.skip_if(libvirt_missing, 'Test requires libvirt')
    def test_fetch_diskio_with_libvirt_non_existent_instance(self):
        instance = mock.MagicMock()
        instance.name = 'instance-00000999'
        instance.id = 999
        counters = list(self.pollster.get_counters(self.manager, instance))
        assert not counters


class TestNetPollster(test_base.TestCase):

    def setUp(self):
        self.manager = manager.AgentManager()
        self.pollster = libvirt.NetPollster()
        super(TestNetPollster, self).setUp()
        self.instance = mock.MagicMock()
        self.instance.name = 'instance-00000001'
        self.instance.id = 1

    def test_get_vnics(self):
        dom_xml = """
             <domain type='kvm'>
                 <devices>
                    <interface type='bridge'>
                       <mac address='fa:16:3e:71:ec:6d'/>
                       <source bridge='br100'/>
                       <target dev='vnet0'/>
                       <filterref filter=
                        'nova-instance-instance-00000001-fa163e71ec6d'>
                         <parameter name='DHCPSERVER' value='10.0.0.1'/>
                         <parameter name='IP' value='10.0.0.2'/>
                         <parameter name='PROJMASK' value='255.255.255.0'/>
                         <parameter name='PROJNET' value='10.0.0.0'/>
                       </filterref>
                       <alias name='net0'/>
                     </interface>
                     <interface type='bridge'>
                       <mac address='fa:16:3e:71:ec:6e'/>
                       <source bridge='br100'/>
                       <target dev='vnet1'/>
                       <filterref filter=
                        'nova-instance-instance-00000001-fa163e71ec6e'>
                         <parameter name='DHCPSERVER' value='192.168.0.1'/>
                         <parameter name='IP' value='192.168.0.2'/>
                         <parameter name='PROJMASK' value='255.255.255.0'/>
                         <parameter name='PROJNET' value='192.168.0.0'/>
                       </filterref>
                       <alias name='net1'/>
                     </interface>
                 </devices>
             </domain>
        """

        ignore = mox.IgnoreArg()
        conn = self.mox.CreateMockAnything()
        domain = self.mox.CreateMockAnything()
        conn._conn = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(conn._conn, 'lookupByName')
        conn._conn.lookupByName(self.instance.name).AndReturn(domain)
        self.mox.StubOutWithMock(domain, 'XMLDesc')
        domain.XMLDesc(0).AndReturn(dom_xml)
        self.mox.ReplayAll()
        interfaces = self.pollster._get_vnics(conn, self.instance)
        self.assertTrue('vnet1' in [x['name'] for x in interfaces])
        self.assertTrue('fa:16:3e:71:ec:6d', [x['mac'] for x in interfaces])
        self.assertTrue([x['dhcpserver'] for x in interfaces])

    def test_get_counters(self):
        interface_stats1 = (3876L, 15L, 0L, 0L, 15830L, 0L, 0L, 0L)
        interface_stats2 = (9999L, 99L, 0L, 0L, 88888L, 0L, 0L, 0L)
        vnics = [
                 {'name': 'vnet0',
                  'ip': '10.0.0.2',
                  'projmask': '255.255.255.0',
                  'projnet': 'proj1',
                  'fref': 'nova-instance-instance-00000001-fa163e71ec6e',
                  'bridge': 'br100',
                  'dhcp_server': '10.0.0.1',
                  'alias': 'net0',
                  'mac': 'fa:16:3e:71:ec:6d'},
                 {'name': 'vnet1',
                  'ip': '192.168.0.3',
                  'projmask': '255.255.255.0',
                  'projnet': 'proj2',
                  'fref': 'nova-instance-instance-00000001-fa163e71ec6f',
                  'bridge': 'br100',
                  'dhcp_server': '192.168.0.1',
                  'fref': '00:00:00:01:1e',
                  'alias': 'net1',
                  'mac': 'fa:16:3e:71:ec:6e'}
                ]

        ignore = mox.IgnoreArg()
        conn = self.mox.CreateMockAnything()
        conn._conn = self.mox.CreateMockAnything()
        domain = self.mox.CreateMockAnything()
        self.mox.StubOutWithMock(libvirt, 'get_libvirt_connection')
        libvirt.get_libvirt_connection().AndReturn(conn)
        self.mox.StubOutWithMock(self.pollster, '_get_vnics')
        self.pollster._get_vnics(ignore, ignore).AndReturn(vnics)
        self.mox.StubOutWithMock(conn._conn, 'lookupByName')
        conn._conn.lookupByName(self.instance.name).AndReturn(domain)
        self.mox.StubOutWithMock(domain, 'interfaceStats')
        domain.interfaceStats('vnet0').AndReturn(interface_stats1)
        domain.interfaceStats('vnet1').AndReturn(interface_stats2)
        self.mox.ReplayAll()

        results = list(self.pollster.get_counters(self.manager, self.instance))
        self.assertTrue([countr.resource_metadata['ip'] for countr in results])
        self.assertTrue([countr.resource_id for countr in results])
