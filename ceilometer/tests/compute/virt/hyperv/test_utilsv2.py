# Copyright 2013 Cloudbase Solutions Srl
#
# Author: Alessandro Pilotti <apilotti@cloudbasesolutions.com>
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

from ceilometer.compute.virt.hyperv import utilsv2 as utilsv2
from ceilometer.compute.virt import inspector
from ceilometer.openstack.common import test


class TestUtilsV2(test.BaseTestCase):

    def setUp(self):
        self._utils = utilsv2.UtilsV2()
        self._utils._conn = mock.MagicMock()
        self._utils._conn_cimv2 = mock.MagicMock()

        super(TestUtilsV2, self).setUp()

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

    def test_get_vnic_metrics(self):
        fake_vm_element_name = "fake_vm_element_name"
        fake_vnic_element_name = "fake_vnic_name"
        fake_vnic_address = "fake_vnic_address"
        fake_vnic_path = "fake_vnic_path"
        fake_rx_bytes = 1000
        fake_tx_bytes = 2000

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

        self._utils._get_metric_values = mock.MagicMock()
        self._utils._get_metric_values.return_value = [fake_rx_bytes,
                                                       fake_tx_bytes]

        vnic_metrics = list(self._utils.get_vnic_metrics(fake_vm_element_name))

        self.assertEqual(1, len(vnic_metrics))
        self.assertEqual(fake_rx_bytes, vnic_metrics[0]['rx_bytes'])
        self.assertEqual(fake_tx_bytes, vnic_metrics[0]['tx_bytes'])
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
        self.assertEqual(long(fake_metric_value), metric_values[0])

    def test_get_vm_setting_data(self):
        mock_vm_s = mock.MagicMock()
        mock_vm_s.VirtualSystemType = self._utils._VIRTUAL_SYSTEM_TYPE_REALIZED

        mock_vm = mock.MagicMock()
        mock_vm.associators.return_value = [mock_vm_s]

        vm_setting_data = self._utils._get_vm_setting_data(mock_vm)

        self.assertEqual(mock_vm_s, vm_setting_data)
