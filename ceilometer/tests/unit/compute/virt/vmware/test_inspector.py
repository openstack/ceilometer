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
from ceilometer import service


class TestVsphereInspection(base.BaseTestCase):

    def setUp(self):
        super(TestVsphereInspection, self).setUp()
        conf = service.prepare_service([], [])
        api_session = api.VMwareAPISession("test_server", "test_user",
                                           "test_password", 0, None,
                                           create_session=False, port=7443)
        vsphere_inspector.get_api_session = mock.Mock(
            return_value=api_session)
        self._inspector = vsphere_inspector.VsphereInspector(conf)
        self._inspector._ops = mock.MagicMock()

    def test_instance_notFound(self):
        test_vm_mobj = mock.MagicMock()
        test_vm_mobj = None
        ops_mock = self._inspector._ops
        ops_mock.get_vm_mobj.return_value = test_vm_mobj
        self.assertRaises(virt_inspector.InstanceNotFoundException,
                          self._inspector._get_vm_mobj_not_power_off_or_raise,
                          mock.MagicMock())

    def test_instance_poweredOff(self):
        test_vm_mobj = mock.MagicMock()
        test_vm_mobj.value = "vm-21"
        test_vm_mobj_powerState = "poweredOff"

        ops_mock = self._inspector._ops
        ops_mock.get_vm_mobj.return_value = test_vm_mobj
        ops_mock.query_vm_property.return_value = test_vm_mobj_powerState
        self.assertRaises(virt_inspector.InstanceShutOffException,
                          self._inspector._get_vm_mobj_not_power_off_or_raise,
                          mock.MagicMock())

    def test_instance_poweredOn(self):
        test_vm_mobj = mock.MagicMock()
        test_vm_mobj.value = "vm-21"
        test_vm_mobj_powerState = "poweredOn"

        ops_mock = self._inspector._ops
        ops_mock.get_vm_mobj.return_value = test_vm_mobj
        ops_mock.query_vm_property.return_value = test_vm_mobj_powerState
        vm_mobj = self._inspector._get_vm_mobj_not_power_off_or_raise(
            mock.MagicMock())
        self.assertEqual(test_vm_mobj.value, vm_mobj.value)

    def test_inspect_memory_usage(self):
        test_vm_mobj = mock.MagicMock()
        test_vm_mobj.value = "vm-21"
        fake_perf_counter_id = 'fake_perf_counter_id'
        fake_memory_value = 1024.0

        self._inspector._get_vm_mobj_not_power_off_or_raise = mock.MagicMock()
        self._inspector._get_vm_mobj_not_power_off_or_raise.return_value = (
            test_vm_mobj)

        ops_mock = self._inspector._ops
        ops_mock.get_perf_counter_id.return_value = fake_perf_counter_id
        ops_mock.query_vm_aggregate_stats.return_value = fake_memory_value
        stats = self._inspector.inspect_instance(mock.MagicMock(), None)
        self.assertEqual(1.0, stats.memory_usage)

    def test_inspect_cpu_util(self):
        test_vm_mobj = mock.MagicMock()
        test_vm_mobj.value = "vm-21"
        fake_perf_counter_id = 'fake_perf_counter_id'
        fake_cpu_util_value = 60

        self._inspector._get_vm_mobj_not_power_off_or_raise = mock.MagicMock()
        self._inspector._get_vm_mobj_not_power_off_or_raise.return_value = (
            test_vm_mobj)

        ops_mock = self._inspector._ops
        ops_mock.get_perf_counter_id.return_value = fake_perf_counter_id
        (ops_mock.query_vm_aggregate_stats.
         return_value) = fake_cpu_util_value * 100
        stats = self._inspector.inspect_instance(mock.MagicMock(), None)
        self.assertEqual(60, stats.cpu_util)

    def test_inspect_vnic_rates(self):

        # construct test data
        test_vm_mobj = mock.MagicMock()
        test_vm_mobj.value = "vm-21"
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

        def query_stat_side_effect(vm_mobj, counter_id, duration):
            # assert inputs
            self.assertEqual(test_vm_mobj.value, vm_mobj.value)
            self.assertIn(counter_id, counter_id_to_stats_map)
            return counter_id_to_stats_map[counter_id]

        self._inspector._get_vm_mobj_not_power_off_or_raise = mock.MagicMock()
        self._inspector._get_vm_mobj_not_power_off_or_raise.return_value = (
            test_vm_mobj)

        # configure vsphere operations mock with the test data
        ops_mock = self._inspector._ops
        ops_mock.get_perf_counter_id.side_effect = get_counter_id_side_effect
        ops_mock.query_vm_device_stats.side_effect = query_stat_side_effect
        result = list(self._inspector.inspect_vnic_rates(
            mock.MagicMock(), None))

        self.assertEqual(1024.0, result[0].rx_bytes_rate)
        self.assertEqual(2048.0, result[0].tx_bytes_rate)
        self.assertEqual(3072.0, result[1].rx_bytes_rate)
        self.assertEqual(4096.0, result[1].tx_bytes_rate)

    def test_inspect_disk_rates(self):
        # construct test data
        test_vm_mobj = mock.MagicMock()
        test_vm_mobj.value = "vm-21"
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

        def query_stat_side_effect(vm_mobj, counter_id, duration):
            # assert inputs
            self.assertEqual(test_vm_mobj.value, vm_mobj.value)
            self.assertIn(counter_id, counter_id_to_stats_map)
            return counter_id_to_stats_map[counter_id]

        self._inspector._get_vm_mobj_not_power_off_or_raise = mock.MagicMock()
        self._inspector._get_vm_mobj_not_power_off_or_raise.return_value = (
            test_vm_mobj)

        # configure vsphere operations mock with the test data
        ops_mock = self._inspector._ops
        ops_mock.get_perf_counter_id.side_effect = get_counter_id_side_effect
        ops_mock.query_vm_device_stats.side_effect = query_stat_side_effect

        result = self._inspector.inspect_disk_rates(mock.MagicMock(), None)

        # validate result
        expected_stats = {
            disk1: virt_inspector.DiskRateStats(disk1, 1024, 300, 5120, 700),
            disk2: virt_inspector.DiskRateStats(disk2, 2048, 400, 6144, 0)
        }

        actual_stats = dict((stats.device, stats) for stats in result)
        self.assertEqual(expected_stats, actual_stats)
