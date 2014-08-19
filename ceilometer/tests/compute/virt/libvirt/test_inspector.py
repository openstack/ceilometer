#!/usr/bin/env python
#
# Copyright 2012 Red Hat, Inc
#
# Author: Eoghan Glynn <eglynn@redhat.com>
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
"""Tests for libvirt inspector.
"""

import contextlib

import fixtures
import mock
from oslotest import base

from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.compute.virt.libvirt import inspector as libvirt_inspector


class TestLibvirtInspection(base.BaseTestCase):

    def setUp(self):
        super(TestLibvirtInspection, self).setUp()
        self.instance_name = 'instance-00000001'
        self.inspector = libvirt_inspector.LibvirtInspector()
        self.inspector.connection = mock.Mock()
        libvirt_inspector.libvirt = mock.Mock()
        libvirt_inspector.libvirt.VIR_DOMAIN_SHUTOFF = 5
        self.domain = mock.Mock()
        self.addCleanup(mock.patch.stopall)

    def test_inspect_instances(self):
        class FakeDomain(object):
            def name(self):
                return 'fake_name'

            def UUIDString(self):
                return 'uuid'

        fake_domain = FakeDomain()
        connection = self.inspector.connection
        with contextlib.nested(mock.patch.object(connection, 'numOfDomains',
                                                 return_value=1),
                               mock.patch.object(connection, 'listDomainsID',
                                                 return_value=[42]),
                               mock.patch.object(connection, 'lookupByID',
                                                 return_value=fake_domain)):
            inspected_instances = list(self.inspector.inspect_instances())
            self.assertEqual(1, len(inspected_instances))
            inspected_instance = inspected_instances[0]
            self.assertEqual('fake_name', inspected_instance.name)
            self.assertEqual('uuid', inspected_instance.UUID)

    def test_inspect_cpus(self):
        with contextlib.nested(mock.patch.object(self.inspector.connection,
                                                 'lookupByName',
                                                 return_value=self.domain),
                               mock.patch.object(self.domain, 'info',
                                                 return_value=(0L, 0L, 0L,
                                                               2L, 999999L))):
                cpu_info = self.inspector.inspect_cpus(self.instance_name)
                self.assertEqual(2L, cpu_info.number)
                self.assertEqual(999999L, cpu_info.time)

    def test_inspect_vnics(self):
        dom_xml = """
             <domain type='kvm'>
                 <devices>
                    <!-- NOTE(dprince): interface with no target -->
                    <interface type='bridge'>
                       <mac address='fa:16:3e:93:31:5a'/>
                       <source bridge='br100'/>
                       <model type='virtio'/>
                       <address type='pci' domain='0x0000' bus='0x00' \
                       slot='0x03' function='0x0'/>
                    </interface>
                    <!-- NOTE(dprince): interface with no mac -->
                    <interface type='bridge'>
                       <source bridge='br100'/>
                       <target dev='foo'/>
                       <model type='virtio'/>
                       <address type='pci' domain='0x0000' bus='0x00' \
                       slot='0x03' function='0x0'/>
                    </interface>
                    <interface type='bridge'>
                       <mac address='fa:16:3e:71:ec:6d'/>
                       <source bridge='br100'/>
                       <target dev='vnet0'/>
                       <filterref filter=
                        'nova-instance-00000001-fa163e71ec6d'>
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
                        'nova-instance-00000001-fa163e71ec6e'>
                         <parameter name='DHCPSERVER' value='192.168.0.1'/>
                         <parameter name='IP' value='192.168.0.2'/>
                         <parameter name='PROJMASK' value='255.255.255.0'/>
                         <parameter name='PROJNET' value='192.168.0.0'/>
                       </filterref>
                       <alias name='net1'/>
                     </interface>
                     <interface type='bridge'>
                       <mac address='fa:16:3e:96:33:f0'/>
                       <source bridge='qbr420008b3-7c'/>
                       <target dev='vnet2'/>
                       <model type='virtio'/>
                       <address type='pci' domain='0x0000' bus='0x00' \
                       slot='0x03' function='0x0'/>
                    </interface>
                 </devices>
             </domain>
        """

        interface_stats = {
            'vnet0': (1L, 2L, 0L, 0L, 3L, 4L, 0L, 0L),
            'vnet1': (5L, 6L, 0L, 0L, 7L, 8L, 0L, 0L),
            'vnet2': (9L, 10L, 0L, 0L, 11L, 12L, 0L, 0L),
        }
        interfaceStats = interface_stats.__getitem__

        connection = self.inspector.connection
        with contextlib.nested(mock.patch.object(connection, 'lookupByName',
                                                 return_value=self.domain),
                               mock.patch.object(self.domain, 'XMLDesc',
                                                 return_value=dom_xml),
                               mock.patch.object(self.domain,
                                                 'interfaceStats',
                                                 side_effect=interfaceStats),
                               mock.patch.object(self.domain, 'info',
                                                 return_value=(0L, 0L, 0L,
                                                               2L, 999999L))):
            interfaces = list(self.inspector.inspect_vnics(self.instance_name))

            self.assertEqual(3, len(interfaces))
            vnic0, info0 = interfaces[0]
            self.assertEqual('vnet0', vnic0.name)
            self.assertEqual('fa:16:3e:71:ec:6d', vnic0.mac)
            self.assertEqual('nova-instance-00000001-fa163e71ec6d', vnic0.fref)
            self.assertEqual('255.255.255.0', vnic0.parameters.get('projmask'))
            self.assertEqual('10.0.0.2', vnic0.parameters.get('ip'))
            self.assertEqual('10.0.0.0', vnic0.parameters.get('projnet'))
            self.assertEqual('10.0.0.1', vnic0.parameters.get('dhcpserver'))
            self.assertEqual(1L, info0.rx_bytes)
            self.assertEqual(2L, info0.rx_packets)
            self.assertEqual(3L, info0.tx_bytes)
            self.assertEqual(4L, info0.tx_packets)

            vnic1, info1 = interfaces[1]
            self.assertEqual('vnet1', vnic1.name)
            self.assertEqual('fa:16:3e:71:ec:6e', vnic1.mac)
            self.assertEqual('nova-instance-00000001-fa163e71ec6e', vnic1.fref)
            self.assertEqual('255.255.255.0', vnic1.parameters.get('projmask'))
            self.assertEqual('192.168.0.2', vnic1.parameters.get('ip'))
            self.assertEqual('192.168.0.0', vnic1.parameters.get('projnet'))
            self.assertEqual('192.168.0.1', vnic1.parameters.get('dhcpserver'))
            self.assertEqual(5L, info1.rx_bytes)
            self.assertEqual(6L, info1.rx_packets)
            self.assertEqual(7L, info1.tx_bytes)
            self.assertEqual(8L, info1.tx_packets)

            vnic2, info2 = interfaces[2]
            self.assertEqual('vnet2', vnic2.name)
            self.assertEqual('fa:16:3e:96:33:f0', vnic2.mac)
            self.assertIsNone(vnic2.fref)
            self.assertEqual(dict(), vnic2.parameters)
            self.assertEqual(9L, info2.rx_bytes)
            self.assertEqual(10L, info2.rx_packets)
            self.assertEqual(11L, info2.tx_bytes)
            self.assertEqual(12L, info2.tx_packets)

    def test_inspect_vnics_with_domain_shutoff(self):
        connection = self.inspector.connection
        with contextlib.nested(mock.patch.object(connection, 'lookupByName',
                                                 return_value=self.domain),
                               mock.patch.object(self.domain, 'info',
                                                 return_value=(5L, 0L, 0L,
                                                               2L, 999999L))):
            interfaces = list(self.inspector.inspect_vnics(self.instance_name))
            self.assertEqual(interfaces, [])

    def test_inspect_disks(self):
        dom_xml = """
             <domain type='kvm'>
                 <devices>
                     <disk type='file' device='disk'>
                         <driver name='qemu' type='qcow2' cache='none'/>
                         <source file='/path/instance-00000001/disk'/>
                         <target dev='vda' bus='virtio'/>
                         <alias name='virtio-disk0'/>
                         <address type='pci' domain='0x0000' bus='0x00'
                                  slot='0x04' function='0x0'/>
                     </disk>
                 </devices>
             </domain>
        """

        with contextlib.nested(mock.patch.object(self.inspector.connection,
                                                 'lookupByName',
                                                 return_value=self.domain),
                               mock.patch.object(self.domain, 'XMLDesc',
                                                 return_value=dom_xml),
                               mock.patch.object(self.domain, 'blockStats',
                                                 return_value=(1L, 2L, 3L,
                                                               4L, -1)),
                               mock.patch.object(self.domain, 'info',
                                                 return_value=(0L, 0L, 0L,
                                                               2L, 999999L))):
                disks = list(self.inspector.inspect_disks(self.instance_name))

                self.assertEqual(1, len(disks))
                disk0, info0 = disks[0]
                self.assertEqual('vda', disk0.device)
                self.assertEqual(1L, info0.read_requests)
                self.assertEqual(2L, info0.read_bytes)
                self.assertEqual(3L, info0.write_requests)
                self.assertEqual(4L, info0.write_bytes)

    def test_inspect_disks_with_domain_shutoff(self):
        connection = self.inspector.connection
        with contextlib.nested(mock.patch.object(connection, 'lookupByName',
                                                 return_value=self.domain),
                               mock.patch.object(self.domain, 'info',
                                                 return_value=(5L, 0L, 0L,
                                                               2L, 999999L))):
            disks = list(self.inspector.inspect_disks(self.instance_name))
            self.assertEqual(disks, [])


class TestLibvirtInspectionWithError(base.BaseTestCase):

    class fakeLibvirtError(Exception):
        pass

    def setUp(self):
        super(TestLibvirtInspectionWithError, self).setUp()
        self.inspector = libvirt_inspector.LibvirtInspector()
        self.useFixture(fixtures.MonkeyPatch(
            'ceilometer.compute.virt.libvirt.inspector.'
            'LibvirtInspector._get_connection',
            self._dummy_get_connection))
        libvirt_inspector.libvirt = mock.Mock()
        libvirt_inspector.libvirt.libvirtError = self.fakeLibvirtError

    def _dummy_get_connection(*args, **kwargs):
        raise Exception('dummy')

    def test_inspect_unknown_error(self):
        self.assertRaises(virt_inspector.InspectorException,
                          self.inspector.inspect_cpus, 'foo')
