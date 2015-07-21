# Copyright (c) 2014 VMware, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
"""
Tests for VMware vSphere inspector.
"""

import mock
from oslo_vmware import api
from oslotest import base

from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.compute.virt.vmware import inspector as vsphere_inspector


class TestVsphereInspection(base.BaseTestCase):

    def setUp(self):
        api_session = api.VMwareAPISession("test_server", "test_user",
                                           "test_password", 0, None,
                                           create_session=False, port=7443)
        vsphere_inspector.get_api_session = mock.Mock(
            return_value=api_session)
        self._inspector = vsphere_inspector.VsphereInspector()
        self._inspector._ops = mock.MagicMock()

        super(TestVsphereInspection, self).setUp()

    def test_inspect_memory_usage(self):
        fake_instance_moid = 'fake_instance_moid'
        fake_instance_id = 'fake_instance_id'
        fake_perf_counter_id = 'fake_perf_counter_id'
        fake_memory_value = 1024.0
        fake_stat = virt_inspector.MemoryUsageStats(usage=1.0)

        def construct_mock_instance_object(fake_instance_id):
            instance_object = mock.MagicMock()
            instance_object.id = fake_instance_id
            return instance_object

        fake_instance = construct_mock_instance_object(fake_instance_id)
        self._inspector._ops.get_vm_moid.return_value = fake_instance_moid
        (self._inspector._ops.
         get_perf_counter_id.return_value) = fake_perf_counter_id
        (self._inspector._ops.query_vm_aggregate_stats.
         return_value) = fake_memory_value
        memory_stat = self._inspector.inspect_memory_usage(fake_instance)
        self.assertEqual(fake_stat, memory_stat)

    def test_inspect_cpu_util(self):
        fake_instance_moid = 'fake_instance_moid'
        fake_instance_id = 'fake_instance_id'
        fake_perf_counter_id = 'fake_perf_counter_id'
        fake_cpu_util_value = 60
        fake_stat = virt_inspector.CPUUtilStats(util=60)

        def construct_mock_instance_object(fake_instance_id):
            instance_object = mock.MagicMock()
            instance_object.id = fake_instance_id
            return instance_object

        fake_instance = construct_mock_instance_object(fake_instance_id)
        self._inspector._ops.get_vm_moid.return_value = fake_instance_moid
        (self._inspector._ops.get_perf_counter_id.
         return_value) = fake_perf_counter_id
        (self._inspector._ops.query_vm_aggregate_stats.
         return_value) = fake_cpu_util_value * 100
        cpu_util_stat = self._inspector.inspect_cpu_util(fake_instance)
        self.assertEqual(fake_stat, cpu_util_stat)

    def test_inspect_vnic_rates(self):

        # construct test data
        test_vm_moid = "vm-21"
        vnic1 = "vnic-1"
        vnic2 = "vnic-2"
        counter_name_to_id_map = {
            vsphere_inspector.VC_NETWORK_RX_COUNTER: 1,
            vsphere_inspector.VC_NETWORK_TX_COUNTER: 2
        }
        counter_id_to_stats_map = {
            1: {vnic1: 1, vnic2: 3},
            2: {vnic1: 2, vnic2: 4},
        }

        def get_counter_id_side_effect(counter_full_name):
            return counter_name_to_id_map[counter_full_name]

        def query_stat_side_effect(vm_moid, counter_id, duration):
            # assert inputs
            self.assertEqual(test_vm_moid, vm_moid)
            self.assertIn(counter_id, counter_id_to_stats_map)
            return counter_id_to_stats_map[counter_id]

        # configure vsphere operations mock with the test data
        ops_mock = self._inspector._ops
        ops_mock.get_vm_moid.return_value = test_vm_moid
        ops_mock.get_perf_counter_id.side_effect = get_counter_id_side_effect
        ops_mock.query_vm_device_stats.side_effect = query_stat_side_effect
        result = self._inspector.inspect_vnic_rates(mock.MagicMock())

        # validate result
        expected_stats = {
            vnic1: virt_inspector.InterfaceRateStats(1024, 2048),
            vnic2: virt_inspector.InterfaceRateStats(3072, 4096)
        }

        for vnic, rates_info in result:
            self.assertEqual(expected_stats[vnic.name], rates_info)

    def test_inspect_disk_rates(self):

        # construct test data
        test_vm_moid = "vm-21"
        disk1 = "disk-1"
        disk2 = "disk-2"
        counter_name_to_id_map = {
            vsphere_inspector.VC_DISK_READ_RATE_CNTR: 1,
            vsphere_inspector.VC_DISK_READ_REQUESTS_RATE_CNTR: 2,
            vsphere_inspector.VC_DISK_WRITE_RATE_CNTR: 3,
            vsphere_inspector.VC_DISK_WRITE_REQUESTS_RATE_CNTR: 4
        }
        counter_id_to_stats_map = {
            1: {disk1: 1, disk2: 2},
            2: {disk1: 300, disk2: 400},
            3: {disk1: 5, disk2: 6},
            4: {disk1: 700},
        }

        def get_counter_id_side_effect(counter_full_name):
            return counter_name_to_id_map[counter_full_name]

        def query_stat_side_effect(vm_moid, counter_id, duration):
            # assert inputs
            self.assertEqual(test_vm_moid, vm_moid)
            self.assertIn(counter_id, counter_id_to_stats_map)
            return counter_id_to_stats_map[counter_id]

        # configure vsphere operations mock with the test data
        ops_mock = self._inspector._ops
        ops_mock.get_vm_moid.return_value = test_vm_moid
        ops_mock.get_perf_counter_id.side_effect = get_counter_id_side_effect
        ops_mock.query_vm_device_stats.side_effect = query_stat_side_effect

        result = self._inspector.inspect_disk_rates(mock.MagicMock())

        # validate result
        expected_stats = {
            disk1: virt_inspector.DiskRateStats(1024, 300, 5120, 700),
            disk2: virt_inspector.DiskRateStats(2048, 400, 6144, 0)
        }

        actual_stats = dict((disk.device, rates) for (disk, rates) in result)
        self.assertEqual(expected_stats, actual_stats)
