# Copyright 2012 Red Hat, Inc
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

import fixtures
import mock
from oslo_config import fixture as fixture_config
from oslo_utils import units
from oslotest import base

from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.compute.virt.libvirt import inspector as libvirt_inspector
from ceilometer.compute.virt.libvirt import utils


class FakeLibvirtError(Exception):
    pass


class VMInstance(object):
    id = 'ff58e738-12f4-4c58-acde-77617b68da56'
    name = 'instance-00000001'


class TestLibvirtInspection(base.BaseTestCase):

    def setUp(self):
        super(TestLibvirtInspection, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf

        self.instance = VMInstance()
        libvirt_inspector.libvirt = mock.Mock()
        libvirt_inspector.libvirt.getVersion.return_value = 5001001
        libvirt_inspector.libvirt.VIR_DOMAIN_SHUTOFF = 5
        libvirt_inspector.libvirt.libvirtError = FakeLibvirtError
        utils.libvirt = libvirt_inspector.libvirt
        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=None):
            self.inspector = libvirt_inspector.LibvirtInspector(self.CONF)

    def test_inspect_instance_stats(self):
        domain = mock.Mock()
        domain.info.return_value = (0, 0, 0, 2, 999999)
        domain.memoryStats.return_value = {'available': 51200,
                                           'unused': 25600,
                                           'rss': 30000}
        conn = mock.Mock()
        conn.lookupByUUIDString.return_value = domain
        conn.domainListGetStats.return_value = [({}, {
            'cpu.time': 999999,
            'vcpu.current': 2,
            'perf.cmt': 90112,
            'perf.cpu_cycles': 7259361,
            'perf.instructions': 8815623,
            'perf.cache_references': 74184,
            'perf.cache_misses': 16737,
            'perf.mbmt': 1892352,
            'perf.mbml': 1802240})]

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            stats = self.inspector.inspect_instance(self.instance)
            self.assertEqual(2, stats.cpu_number)
            self.assertEqual(999999, stats.cpu_time)
            self.assertEqual(90112, stats.cpu_l3_cache_usage)
            self.assertEqual(25600 / units.Ki, stats.memory_usage)
            self.assertEqual(30000 / units.Ki, stats.memory_resident)
            self.assertEqual(1892352, stats.memory_bandwidth_total)
            self.assertEqual(1802240, stats.memory_bandwidth_local)
            self.assertEqual(7259361, stats.cpu_cycles)
            self.assertEqual(8815623, stats.instructions)
            self.assertEqual(74184, stats.cache_references)
            self.assertEqual(16737, stats.cache_misses)

    def test_inspect_cpus_with_domain_shutoff(self):
        domain = mock.Mock()
        domain.info.return_value = (5, 0, 0, 2, 999999)
        conn = mock.Mock()
        conn.lookupByUUIDString.return_value = domain

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            self.assertRaises(virt_inspector.InstanceShutOffException,
                              self.inspector.inspect_instance,
                              self.instance)

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
            'vnet0': (1, 2, 0, 0, 3, 4, 0, 0),
            'vnet1': (5, 6, 0, 0, 7, 8, 0, 0),
            'vnet2': (9, 10, 0, 0, 11, 12, 0, 0),
        }
        interfaceStats = interface_stats.__getitem__

        domain = mock.Mock()
        domain.XMLDesc.return_value = dom_xml
        domain.info.return_value = (0, 0, 0, 2, 999999)
        domain.interfaceStats.side_effect = interfaceStats
        conn = mock.Mock()
        conn.lookupByUUIDString.return_value = domain

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            interfaces = list(self.inspector.inspect_vnics(self.instance))

            self.assertEqual(3, len(interfaces))
            vnic0, info0 = interfaces[0]
            self.assertEqual('vnet0', vnic0.name)
            self.assertEqual('fa:16:3e:71:ec:6d', vnic0.mac)
            self.assertEqual('nova-instance-00000001-fa163e71ec6d', vnic0.fref)
            self.assertEqual('255.255.255.0', vnic0.parameters.get('projmask'))
            self.assertEqual('10.0.0.2', vnic0.parameters.get('ip'))
            self.assertEqual('10.0.0.0', vnic0.parameters.get('projnet'))
            self.assertEqual('10.0.0.1', vnic0.parameters.get('dhcpserver'))
            self.assertEqual(1, info0.rx_bytes)
            self.assertEqual(2, info0.rx_packets)
            self.assertEqual(3, info0.tx_bytes)
            self.assertEqual(4, info0.tx_packets)

            vnic1, info1 = interfaces[1]
            self.assertEqual('vnet1', vnic1.name)
            self.assertEqual('fa:16:3e:71:ec:6e', vnic1.mac)
            self.assertEqual('nova-instance-00000001-fa163e71ec6e', vnic1.fref)
            self.assertEqual('255.255.255.0', vnic1.parameters.get('projmask'))
            self.assertEqual('192.168.0.2', vnic1.parameters.get('ip'))
            self.assertEqual('192.168.0.0', vnic1.parameters.get('projnet'))
            self.assertEqual('192.168.0.1', vnic1.parameters.get('dhcpserver'))
            self.assertEqual(5, info1.rx_bytes)
            self.assertEqual(6, info1.rx_packets)
            self.assertEqual(7, info1.tx_bytes)
            self.assertEqual(8, info1.tx_packets)

            vnic2, info2 = interfaces[2]
            self.assertEqual('vnet2', vnic2.name)
            self.assertEqual('fa:16:3e:96:33:f0', vnic2.mac)
            self.assertIsNone(vnic2.fref)
            self.assertEqual(dict(), vnic2.parameters)
            self.assertEqual(9, info2.rx_bytes)
            self.assertEqual(10, info2.rx_packets)
            self.assertEqual(11, info2.tx_bytes)
            self.assertEqual(12, info2.tx_packets)

    def test_inspect_vnics_with_domain_shutoff(self):
        domain = mock.Mock()
        domain.info.return_value = (5, 0, 0, 2, 999999)
        conn = mock.Mock()
        conn.lookupByUUIDString.return_value = domain

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            inspect = self.inspector.inspect_vnics
            self.assertRaises(virt_inspector.InstanceShutOffException,
                              list, inspect(self.instance))

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
        domain = mock.Mock()
        domain.XMLDesc.return_value = dom_xml
        domain.info.return_value = (0, 0, 0, 2, 999999)
        domain.blockStats.return_value = (1, 2, 3, 4, -1)
        conn = mock.Mock()
        conn.lookupByUUIDString.return_value = domain

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            disks = list(self.inspector.inspect_disks(self.instance))

            self.assertEqual(1, len(disks))
            disk0, info0 = disks[0]
            self.assertEqual('vda', disk0.device)
            self.assertEqual(1, info0.read_requests)
            self.assertEqual(2, info0.read_bytes)
            self.assertEqual(3, info0.write_requests)
            self.assertEqual(4, info0.write_bytes)

    def test_inspect_disks_with_domain_shutoff(self):
        domain = mock.Mock()
        domain.info.return_value = (5, 0, 0, 2, 999999)
        conn = mock.Mock()
        conn.lookupByUUIDString.return_value = domain

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            inspect = self.inspector.inspect_disks
            self.assertRaises(virt_inspector.InstanceShutOffException,
                              list, inspect(self.instance))

    def test_inspect_disk_info(self):
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
        domain = mock.Mock()
        domain.XMLDesc.return_value = dom_xml
        domain.blockInfo.return_value = (1, 2, 3, -1)
        domain.info.return_value = (0, 0, 0, 2, 999999)
        conn = mock.Mock()
        conn.lookupByUUIDString.return_value = domain

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            disks = list(self.inspector.inspect_disk_info(self.instance))

            self.assertEqual(1, len(disks))
            disk0, info0 = disks[0]
            self.assertEqual('vda', disk0.device)
            self.assertEqual(1, info0.capacity)
            self.assertEqual(2, info0.allocation)
            self.assertEqual(3, info0.physical)

    def test_inspect_disk_info_network_type(self):
        dom_xml = """
             <domain type='kvm'>
                 <devices>
                     <disk type='network' device='disk'>
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
        domain = mock.Mock()
        domain.XMLDesc.return_value = dom_xml
        domain.blockInfo.return_value = (1, 2, 3, -1)
        domain.info.return_value = (0, 0, 0, 2, 999999)
        conn = mock.Mock()
        conn.lookupByUUIDString.return_value = domain

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            disks = list(self.inspector.inspect_disk_info(self.instance))
            self.assertEqual(0, len(disks))

    def test_inspect_disk_info_without_source_element(self):
        dom_xml = """
             <domain type='kvm'>
                 <devices>
                    <disk type='file' device='cdrom'>
                        <driver name='qemu' type='raw' cache='none'/>
                        <backingStore/>
                        <target dev='hdd' bus='ide' tray='open'/>
                        <readonly/>
                        <alias name='ide0-1-1'/>
                        <address type='drive' controller='0' bus='1'
                                 target='0' unit='1'/>
                     </disk>
                 </devices>
             </domain>
        """
        domain = mock.Mock()
        domain.XMLDesc.return_value = dom_xml
        domain.blockInfo.return_value = (1, 2, 3, -1)
        domain.info.return_value = (0, 0, 0, 2, 999999)
        conn = mock.Mock()
        conn.lookupByUUIDString.return_value = domain

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            disks = list(self.inspector.inspect_disk_info(self.instance))
            self.assertEqual(0, len(disks))

    def test_inspect_memory_usage_with_domain_shutoff(self):
        domain = mock.Mock()
        domain.info.return_value = (5, 0, 51200, 2, 999999)
        conn = mock.Mock()
        conn.lookupByUUIDString.return_value = domain

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            self.assertRaises(virt_inspector.InstanceShutOffException,
                              self.inspector.inspect_instance,
                              self.instance)

    def test_inspect_memory_with_empty_stats(self):
        domain = mock.Mock()
        domain.info.return_value = (0, 0, 51200, 2, 999999)
        domain.memoryStats.return_value = {}
        conn = mock.Mock()
        conn.domainListGetStats.return_value = [({}, {})]
        conn.lookupByUUIDString.return_value = domain

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            stats = self.inspector.inspect_instance(self.instance)
            self.assertIsNone(stats.memory_usage)
            self.assertIsNone(stats.memory_resident)

    def test_inspect_perf_events_libvirt_less_than_2_3_0(self):
        domain = mock.Mock()
        domain.info.return_value = (0, 0, 51200, 2, 999999)
        domain.memoryStats.return_value = {'rss': 0,
                                           'available': 51200,
                                           'unused': 25600}
        conn = mock.Mock()
        conn.domainListGetStats.return_value = [({}, {})]
        conn.lookupByUUIDString.return_value = domain

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            stats = self.inspector.inspect_instance(self.instance)
            self.assertIsNone(stats.cpu_l3_cache_usage)
            self.assertIsNone(stats.memory_bandwidth_total)
            self.assertIsNone(stats.memory_bandwidth_local)
            self.assertIsNone(stats.cpu_cycles)
            self.assertIsNone(stats.instructions)
            self.assertIsNone(stats.cache_references)
            self.assertIsNone(stats.cache_misses)


class TestLibvirtInspectionWithError(base.BaseTestCase):

    def setUp(self):
        super(TestLibvirtInspectionWithError, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.useFixture(fixtures.MonkeyPatch(
            'ceilometer.compute.virt.libvirt.utils.'
            'refresh_libvirt_connection',
            mock.MagicMock(side_effect=[None, Exception('dummy')])))
        libvirt_inspector.libvirt = mock.Mock()
        libvirt_inspector.libvirt.libvirtError = FakeLibvirtError
        utils.libvirt = libvirt_inspector.libvirt
        self.inspector = libvirt_inspector.LibvirtInspector(self.CONF)

    def test_inspect_unknown_error(self):
        self.assertRaises(virt_inspector.InspectorException,
                          self.inspector.inspect_instance, 'foo')
