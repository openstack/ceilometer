# Copyright 2013 Cloudbase Solutions Srl
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
"""
Tests for Hyper-V utilsv2.
"""

import mock
from oslotest import base

from ceilometer.compute.virt.hyperv import utilsv2 as utilsv2
from ceilometer.compute.virt import inspector


class TestUtilsV2(base.BaseTestCase):

    _FAKE_RETURN_CLASS = 'fake_return_class'

    def setUp(self):
        self._utils = utilsv2.UtilsV2()
        self._utils._conn = mock.MagicMock()
        self._utils._conn_cimv2 = mock.MagicMock()

        super(TestUtilsV2, self).setUp()

    @mock.patch.object(utilsv2.UtilsV2, '_get_metrics')
    @mock.patch.object(utilsv2.UtilsV2, '_get_metric_def')
    @mock.patch.object(utilsv2.UtilsV2, '_lookup_vm')
    def test_get_memory_metrics(self, mock_lookup_vm, mock_get_metric_def,
                                mock_get_metrics):
        mock_vm = mock_lookup_vm.return_value

        mock_metric_def = mock_get_metric_def.return_value

        metric_memory = mock.MagicMock()
        metric_memory.MetricValue = 3
        mock_get_metrics.return_value = [metric_memory]

        response = self._utils.get_memory_metrics(mock.sentinel._FAKE_INSTANCE)

        mock_lookup_vm.assert_called_once_with(mock.sentinel._FAKE_INSTANCE)
        mock_get_metric_def.assert_called_once_with(
            self._utils._MEMORY_METRIC_NAME)
        mock_get_metrics.assert_called_once_with(mock_vm, mock_metric_def)

        self.assertEqual(3, response)

    def test_get_host_cpu_info(self):
        _fake_clock_speed = 1000
        _fake_cpu_count = 2

        mock_cpu = mock.MagicMock()
        mock_cpu.MaxClockSpeed = _fake_clock_speed

        self._utils._conn_cimv2.Win32_Processor.return_value = [mock_cpu,
                                                                mock_cpu]
        cpu_info = self._utils.get_host_cpu_info()

        self.assertEqual(_fake_clock_speed, cpu_info[0])
        self.assertEqual(_fake_cpu_count, cpu_info[1])

    def test_get_all_vms(self):
        fake_vm_element_name = "fake_vm_element_name"
        fake_vm_name = "fake_vm_name"

        mock_vm = mock.MagicMock()
        mock_vm.ElementName = fake_vm_element_name
        mock_vm.Name = fake_vm_name
        self._utils._conn.Msvm_ComputerSystem.return_value = [mock_vm]

        vms = self._utils.get_all_vms()

        self.assertEqual((fake_vm_element_name, fake_vm_name), vms[0])

    def test_get_cpu_metrics(self):
        fake_vm_element_name = "fake_vm_element_name"
        fake_cpu_count = 2
        fake_uptime = 1000
        fake_cpu_metric_val = 2000

        self._utils._lookup_vm = mock.MagicMock()
        self._utils._lookup_vm().OnTimeInMilliseconds = fake_uptime

        self._utils._get_vm_resources = mock.MagicMock()
        mock_res = self._utils._get_vm_resources()[0]
        mock_res.VirtualQuantity = fake_cpu_count

        self._utils._get_metrics = mock.MagicMock()
        self._utils._get_metrics()[0].MetricValue = fake_cpu_metric_val

        cpu_metrics = self._utils.get_cpu_metrics(fake_vm_element_name)

        self.assertEqual(3, len(cpu_metrics))
        self.assertEqual(fake_cpu_metric_val, cpu_metrics[0])
        self.assertEqual(fake_cpu_count, cpu_metrics[1])
        self.assertEqual(fake_uptime, cpu_metrics[2])

    @mock.patch('ceilometer.compute.virt.hyperv.utilsv2.UtilsV2'
                '._sum_metric_values_by_defs')
    @mock.patch('ceilometer.compute.virt.hyperv.utilsv2.UtilsV2'
                '._get_metric_value_instances')
    def test_get_vnic_metrics(self, mock_get_instances, mock_get_by_defs):
        fake_vm_element_name = "fake_vm_element_name"
        fake_vnic_element_name = "fake_vnic_name"
        fake_vnic_address = "fake_vnic_address"
        fake_vnic_path = "fake_vnic_path"
        fake_rx_mb = 1000
        fake_tx_mb = 2000

        self._utils._lookup_vm = mock.MagicMock()
        self._utils._get_vm_resources = mock.MagicMock()

        mock_port = mock.MagicMock()
        mock_port.Parent = fake_vnic_path

        mock_vnic = mock.MagicMock()
        mock_vnic.path_.return_value = fake_vnic_path
        mock_vnic.ElementName = fake_vnic_element_name
        mock_vnic.Address = fake_vnic_address

        self._utils._get_vm_resources.side_effect = [[mock_port], [mock_vnic]]

        self._utils._get_metric_def = mock.MagicMock()

        mock_get_by_defs.return_value = [fake_rx_mb, fake_tx_mb]

        vnic_metrics = list(self._utils.get_vnic_metrics(fake_vm_element_name))

        self.assertEqual(1, len(vnic_metrics))
        self.assertEqual(fake_rx_mb, vnic_metrics[0]['rx_mb'])
        self.assertEqual(fake_tx_mb, vnic_metrics[0]['tx_mb'])
        self.assertEqual(fake_vnic_element_name,
                         vnic_metrics[0]['element_name'])
        self.assertEqual(fake_vnic_address, vnic_metrics[0]['address'])

    def test_get_disk_metrics(self):
        fake_vm_element_name = "fake_vm_element_name"
        fake_host_resource = "fake_host_resource"
        fake_instance_id = "fake_instance_id"
        fake_read_mb = 1000
        fake_write_mb = 2000

        self._utils._lookup_vm = mock.MagicMock()

        mock_disk = mock.MagicMock()
        mock_disk.HostResource = [fake_host_resource]
        mock_disk.InstanceID = fake_instance_id
        self._utils._get_vm_resources = mock.MagicMock(
            return_value=[mock_disk])

        self._utils._get_metric_def = mock.MagicMock()

        self._utils._get_metric_values = mock.MagicMock()
        self._utils._get_metric_values.return_value = [fake_read_mb,
                                                       fake_write_mb]

        disk_metrics = list(self._utils.get_disk_metrics(fake_vm_element_name))

        self.assertEqual(1, len(disk_metrics))
        self.assertEqual(fake_read_mb, disk_metrics[0]['read_mb'])
        self.assertEqual(fake_write_mb, disk_metrics[0]['write_mb'])
        self.assertEqual(fake_instance_id, disk_metrics[0]['instance_id'])
        self.assertEqual(fake_host_resource, disk_metrics[0]['host_resource'])

    def test_get_disk_latency(self):
        fake_vm_name = mock.sentinel.VM_NAME
        fake_instance_id = mock.sentinel.FAKE_INSTANCE_ID
        fake_latency = mock.sentinel.FAKE_LATENCY

        self._utils._lookup_vm = mock.MagicMock()

        mock_disk = mock.MagicMock()
        mock_disk.InstanceID = fake_instance_id
        self._utils._get_vm_resources = mock.MagicMock(
            return_value=[mock_disk])

        self._utils._get_metric_values = mock.MagicMock(
            return_value=[fake_latency])

        disk_metrics = list(self._utils.get_disk_latency_metrics(fake_vm_name))

        self.assertEqual(1, len(disk_metrics))
        self.assertEqual(fake_latency, disk_metrics[0]['disk_latency'])
        self.assertEqual(fake_instance_id, disk_metrics[0]['instance_id'])

    def test_get_disk_iops_metrics(self):
        fake_vm_name = mock.sentinel.VM_NAME
        fake_instance_id = mock.sentinel.FAKE_INSTANCE_ID
        fake_iops_count = mock.sentinel.FAKE_IOPS_COUNT

        self._utils._lookup_vm = mock.MagicMock()

        mock_disk = mock.MagicMock()
        mock_disk.InstanceID = fake_instance_id
        self._utils._get_vm_resources = mock.MagicMock(
            return_value=[mock_disk])

        self._utils._get_metric_values = mock.MagicMock(
            return_value=[fake_iops_count])

        disk_metrics = list(self._utils.get_disk_iops_count(fake_vm_name))

        self.assertEqual(1, len(disk_metrics))
        self.assertEqual(fake_iops_count, disk_metrics[0]['iops_count'])
        self.assertEqual(fake_instance_id, disk_metrics[0]['instance_id'])

    def test_get_metric_value_instances(self):
        mock_el1 = mock.MagicMock()
        mock_associator = mock.MagicMock()
        mock_el1.associators.return_value = [mock_associator]

        mock_el2 = mock.MagicMock()
        mock_el2.associators.return_value = []

        returned = self._utils._get_metric_value_instances(
            [mock_el1, mock_el2], self._FAKE_RETURN_CLASS)

        self.assertEqual([mock_associator], returned)

    def test_lookup_vm(self):
        fake_vm_element_name = "fake_vm_element_name"
        fake_vm = "fake_vm"
        self._utils._conn.Msvm_ComputerSystem.return_value = [fake_vm]

        vm = self._utils._lookup_vm(fake_vm_element_name)

        self.assertEqual(fake_vm, vm)

    def test_lookup_vm_not_found(self):
        fake_vm_element_name = "fake_vm_element_name"
        self._utils._conn.Msvm_ComputerSystem.return_value = []

        self.assertRaises(inspector.InstanceNotFoundException,
                          self._utils._lookup_vm, fake_vm_element_name)

    def test_lookup_vm_duplicate_found(self):
        fake_vm_element_name = "fake_vm_element_name"
        fake_vm = "fake_vm"
        self._utils._conn.Msvm_ComputerSystem.return_value = [fake_vm, fake_vm]

        self.assertRaises(utilsv2.HyperVException,
                          self._utils._lookup_vm, fake_vm_element_name)

    def test_get_metric_values(self):
        fake_metric_def_id = "fake_metric_def_id"
        fake_metric_value = "1000"

        mock_metric = mock.MagicMock()
        mock_metric.MetricDefinitionId = fake_metric_def_id
        mock_metric.MetricValue = fake_metric_value

        mock_element = mock.MagicMock()
        mock_element.associators.return_value = [mock_metric]

        mock_metric_def = mock.MagicMock()
        mock_metric_def.Id = fake_metric_def_id

        metric_values = self._utils._get_metric_values(mock_element,
                                                       [mock_metric_def])

        self.assertEqual(1, len(metric_values))
        self.assertEqual(int(fake_metric_value), metric_values[0])

    def test_get_vm_setting_data(self):
        mock_vm_s = mock.MagicMock()
        mock_vm_s.VirtualSystemType = self._utils._VIRTUAL_SYSTEM_TYPE_REALIZED

        mock_vm = mock.MagicMock()
        mock_vm.associators.return_value = [mock_vm_s]

        vm_setting_data = self._utils._get_vm_setting_data(mock_vm)

        self.assertEqual(mock_vm_s, vm_setting_data)
