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
from oslo_utils import units
from oslotest import base

from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.compute.virt.libvirt import inspector as libvirt_inspector
from ceilometer.compute.virt.libvirt import utils
from ceilometer import service


class FakeLibvirtError(Exception):
    pass


class VMInstance(object):
    id = 'ff58e738-12f4-4c58-acde-77617b68da56'
    name = 'instance-00000001'


class TestLibvirtInspection(base.BaseTestCase):

    def setUp(self):
        super(TestLibvirtInspection, self).setUp()
        conf = service.prepare_service([], [])

        self.instance = VMInstance()
        libvirt_inspector.libvirt = mock.Mock()
        libvirt_inspector.libvirt.getVersion.return_value = 5001001
        libvirt_inspector.libvirt.VIR_DOMAIN_SHUTOFF = 5
        libvirt_inspector.libvirt.libvirtError = FakeLibvirtError
        utils.libvirt = libvirt_inspector.libvirt
        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=None):
            self.inspector = libvirt_inspector.LibvirtInspector(conf)

    def test_inspect_instance_stats(self):
        domain = mock.Mock()
        domain.info.return_value = (0, 0, 0, 2, 999999)
        domain.memoryStats.return_value = {'available': 51200,
                                           'unused': 25600,
                                           'rss': 30000,
                                           'swap_in': 5120,
                                           'swap_out': 8192}
        conn = mock.Mock()
        conn.lookupByUUIDString.return_value = domain
        conn.domainListGetStats.return_value = [({}, {
            'cpu.time': 999999,
            'vcpu.maximum': 4,
            'vcpu.current': 2,
            'vcpu.0.time': 10000,
            'vcpu.0.wait': 10000,
            'vcpu.2.time': 10000,
            'vcpu.2.wait': 10000,
            'perf.cmt': 90112,
            'perf.cpu_cycles': 7259361,
            'perf.instructions': 8815623,
            'perf.cache_references': 74184,
            'perf.cache_misses': 16737,
            'perf.mbmt': 1892352,
            'perf.mbml': 1802240})]

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            stats = self.inspector.inspect_instance(self.instance, None)
            self.assertEqual(2, stats.cpu_number)
            self.assertEqual(40000, stats.cpu_time)
            self.assertEqual(90112, stats.cpu_l3_cache_usage)
            self.assertEqual(25600 / units.Ki, stats.memory_usage)
            self.assertEqual(30000 / units.Ki, stats.memory_resident)
            self.assertEqual(5120 / units.Ki, stats.memory_swap_in)
            self.assertEqual(8192 / units.Ki, stats.memory_swap_out)
            self.assertEqual(1892352, stats.memory_bandwidth_total)
            self.assertEqual(1802240, stats.memory_bandwidth_local)
            self.assertEqual(7259361, stats.cpu_cycles)
            self.assertEqual(8815623, stats.instructions)
            self.assertEqual(74184, stats.cache_references)
            self.assertEqual(16737, stats.cache_misses)

    def test_inspect_instance_stats_fallback_cpu_time(self):
        domain = mock.Mock()
        domain.info.return_value = (0, 0, 0, 2, 20000)
        domain.memoryStats.return_value = {'available': 51200,
                                           'unused': 25600,
                                           'rss': 30000}
        conn = mock.Mock()
        conn.lookupByUUIDString.return_value = domain
        conn.domainListGetStats.return_value = [({}, {
            'vcpu.current': 2,
            'vcpu.maximum': 4,
            'vcpu.0.time': 10000,
            'vcpu.1.time': 10000,
            'cpu.time': 999999})]

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            stats = self.inspector.inspect_instance(self.instance)
            self.assertEqual(2, stats.cpu_number)
            self.assertEqual(999999, stats.cpu_time)

    def test_inspect_cpus_with_domain_shutoff(self):
        domain = mock.Mock()
        domain.info.return_value = (5, 0, 0, 2, 999999)
        conn = mock.Mock()
        conn.lookupByUUIDString.return_value = domain

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            self.assertRaises(virt_inspector.InstanceShutOffException,
                              self.inspector.inspect_instance,
                              self.instance, None)

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
            'vnet0': (1, 2, 21, 22, 3, 4, 23, 24),
            'vnet1': (5, 6, 25, 26, 7, 8, 27, 28),
            'vnet2': (9, 10, 29, 30, 11, 12, 31, 32),
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
            interfaces = list(self.inspector.inspect_vnics(
                self.instance, None))

            self.assertEqual(3, len(interfaces))
            vnic0 = interfaces[0]
            self.assertEqual('vnet0', vnic0.name)
            self.assertEqual('fa:16:3e:71:ec:6d', vnic0.mac)
            self.assertEqual('nova-instance-00000001-fa163e71ec6d', vnic0.fref)
            self.assertEqual('255.255.255.0', vnic0.parameters.get('projmask'))
            self.assertEqual('10.0.0.2', vnic0.parameters.get('ip'))
            self.assertEqual('10.0.0.0', vnic0.parameters.get('projnet'))
            self.assertEqual('10.0.0.1', vnic0.parameters.get('dhcpserver'))
            self.assertEqual(1, vnic0.rx_bytes)
            self.assertEqual(2, vnic0.rx_packets)
            self.assertEqual(3, vnic0.tx_bytes)
            self.assertEqual(4, vnic0.tx_packets)
            self.assertEqual(21, vnic0.rx_errors)
            self.assertEqual(22, vnic0.rx_drop)
            self.assertEqual(23, vnic0.tx_errors)
            self.assertEqual(24, vnic0.tx_drop)

            vnic1 = interfaces[1]
            self.assertEqual('vnet1', vnic1.name)
            self.assertEqual('fa:16:3e:71:ec:6e', vnic1.mac)
            self.assertEqual('nova-instance-00000001-fa163e71ec6e', vnic1.fref)
            self.assertEqual('255.255.255.0', vnic1.parameters.get('projmask'))
            self.assertEqual('192.168.0.2', vnic1.parameters.get('ip'))
            self.assertEqual('192.168.0.0', vnic1.parameters.get('projnet'))
            self.assertEqual('192.168.0.1', vnic1.parameters.get('dhcpserver'))
            self.assertEqual(5, vnic1.rx_bytes)
            self.assertEqual(6, vnic1.rx_packets)
            self.assertEqual(7, vnic1.tx_bytes)
            self.assertEqual(8, vnic1.tx_packets)
            self.assertEqual(25, vnic1.rx_errors)
            self.assertEqual(26, vnic1.rx_drop)
            self.assertEqual(27, vnic1.tx_errors)
            self.assertEqual(28, vnic1.tx_drop)

            vnic2 = interfaces[2]
            self.assertEqual('vnet2', vnic2.name)
            self.assertEqual('fa:16:3e:96:33:f0', vnic2.mac)
            self.assertIsNone(vnic2.fref)
            self.assertEqual(dict(), vnic2.parameters)
            self.assertEqual(9, vnic2.rx_bytes)
            self.assertEqual(10, vnic2.rx_packets)
            self.assertEqual(11, vnic2.tx_bytes)
            self.assertEqual(12, vnic2.tx_packets)
            self.assertEqual(29, vnic2.rx_errors)
            self.assertEqual(30, vnic2.rx_drop)
            self.assertEqual(31, vnic2.tx_errors)
            self.assertEqual(32, vnic2.tx_drop)

    def test_inspect_vnics_with_domain_shutoff(self):
        domain = mock.Mock()
        domain.info.return_value = (5, 0, 0, 2, 999999)
        conn = mock.Mock()
        conn.lookupByUUIDString.return_value = domain

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            inspect = self.inspector.inspect_vnics
            self.assertRaises(virt_inspector.InstanceShutOffException,
                              list, inspect(self.instance, None))

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
            disks = list(self.inspector.inspect_disks(self.instance, None))

            self.assertEqual(1, len(disks))
            self.assertEqual('vda', disks[0].device)
            self.assertEqual(1, disks[0].read_requests)
            self.assertEqual(2, disks[0].read_bytes)
            self.assertEqual(3, disks[0].write_requests)
            self.assertEqual(4, disks[0].write_bytes)

    def test_inspect_disks_with_domain_shutoff(self):
        domain = mock.Mock()
        domain.info.return_value = (5, 0, 0, 2, 999999)
        conn = mock.Mock()
        conn.lookupByUUIDString.return_value = domain

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            inspect = self.inspector.inspect_disks
            self.assertRaises(virt_inspector.InstanceShutOffException,
                              list, inspect(self.instance, None))

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
            disks = list(self.inspector.inspect_disk_info(
                self.instance, None))

            self.assertEqual(1, len(disks))
            self.assertEqual('vda', disks[0].device)
            self.assertEqual(1, disks[0].capacity)
            self.assertEqual(2, disks[0].allocation)
            self.assertEqual(3, disks[0].physical)

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
            disks = list(self.inspector.inspect_disk_info(self.instance, None))
            self.assertEqual(1, len(disks))

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
            disks = list(self.inspector.inspect_disk_info(self.instance, None))
            self.assertEqual(0, len(disks))

    def test_inspect_disks_without_source_element(self):
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
        blockStatsFlags = {'wr_total_times': 91752302267,
                           'rd_operations': 6756,
                           'flush_total_times': 1310427331,
                           'rd_total_times': 29142253616,
                           'rd_bytes': 171460096,
                           'flush_operations': 746,
                           'wr_operations': 1437,
                           'wr_bytes': 13574656}
        domain = mock.Mock()
        domain.XMLDesc.return_value = dom_xml
        domain.info.return_value = (0, 0, 0, 2, 999999)
        domain.blockStats.return_value = (1, 2, 3, 4, -1)
        domain.blockStatsFlags.return_value = blockStatsFlags
        conn = mock.Mock()
        conn.lookupByUUIDString.return_value = domain

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            disks = list(self.inspector.inspect_disks(self.instance, None))

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
                              self.instance, None)

    def test_inspect_memory_with_empty_stats(self):
        domain = mock.Mock()
        domain.info.return_value = (0, 0, 51200, 2, 999999)
        domain.memoryStats.return_value = {}
        conn = mock.Mock()
        conn.domainListGetStats.return_value = [({}, {})]
        conn.lookupByUUIDString.return_value = domain

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            stats = self.inspector.inspect_instance(self.instance, None)
            self.assertIsNone(stats.memory_usage)
            self.assertIsNone(stats.memory_resident)
            self.assertIsNone(stats.memory_swap_in)
            self.assertIsNone(stats.memory_swap_out)

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
            stats = self.inspector.inspect_instance(self.instance, None)
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
        conf = service.prepare_service([], [])
        self.useFixture(fixtures.MonkeyPatch(
            'ceilometer.compute.virt.libvirt.utils.'
            'refresh_libvirt_connection',
            mock.MagicMock(side_effect=[None, Exception('dummy')])))
        libvirt_inspector.libvirt = mock.Mock()
        libvirt_inspector.libvirt.libvirtError = FakeLibvirtError
        utils.libvirt = libvirt_inspector.libvirt
        self.inspector = libvirt_inspector.LibvirtInspector(conf)

    def test_inspect_unknown_error(self):
        self.assertRaises(virt_inspector.InspectorException,
                          self.inspector.inspect_instance, 'foo', None)
