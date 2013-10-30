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
Tests for Hyper-V inspector.
"""

import mock

from ceilometer.compute.virt.hyperv import inspector as hyperv_inspector
from ceilometer.openstack.common import test


class TestHyperVInspection(test.BaseTestCase):

    def setUp(self):
        self._inspector = hyperv_inspector.HyperVInspector()
        self._inspector._utils = mock.MagicMock()

        super(TestHyperVInspection, self).setUp()

    def test_inspect_instances(self):
        fake_name = 'fake_name'
        fake_uuid = 'fake_uuid'
        fake_instances = [(fake_name, fake_uuid)]
        self._inspector._utils.get_all_vms.return_value = fake_instances

        inspected_instances = list(self._inspector.inspect_instances())

        self.assertEqual(1, len(inspected_instances))
        self.assertEqual(fake_name, inspected_instances[0].name)
        self.assertEqual(fake_uuid, inspected_instances[0].UUID)

    def test_inspect_cpus(self):
        fake_instance_name = 'fake_instance_name'
        fake_host_cpu_clock = 1000
        fake_host_cpu_count = 2
        fake_cpu_clock_used = 2000
        fake_cpu_count = 3000
        fake_uptime = 4000

        fake_cpu_percent_used = (fake_cpu_clock_used /
                                 float(fake_host_cpu_clock * fake_cpu_count))
        fake_cpu_time = (long(fake_uptime * fake_cpu_percent_used) *
                         1000)

        self._inspector._utils.get_host_cpu_info.return_value = (
            fake_host_cpu_clock, fake_host_cpu_count)

        self._inspector._utils.get_cpu_metrics.return_value = (
            fake_cpu_clock_used, fake_cpu_count, fake_uptime)

        cpu_stats = self._inspector.inspect_cpus(fake_instance_name)

        self.assertEqual(fake_cpu_count, cpu_stats.number)
        self.assertEqual(fake_cpu_time, cpu_stats.time)

    def test_inspect_vnics(self):
        fake_instance_name = 'fake_instance_name'
        fake_rx_bytes = 1000
        fake_tx_bytes = 2000
        fake_element_name = 'fake_element_name'
        fake_address = 'fake_address'

        self._inspector._utils.get_vnic_metrics.return_value = [{
            'rx_bytes': fake_rx_bytes,
            'tx_bytes': fake_tx_bytes,
            'element_name': fake_element_name,
            'address': fake_address}]

        inspected_vnics = list(self._inspector.inspect_vnics(
            fake_instance_name))

        self.assertEqual(1, len(inspected_vnics))
        self.assertEqual(2, len(inspected_vnics[0]))

        inspected_vnic, inspected_stats = inspected_vnics[0]

        self.assertEqual(fake_element_name, inspected_vnic.name)
        self.assertEqual(fake_address, inspected_vnic.mac)

        self.assertEqual(fake_rx_bytes, inspected_stats.rx_bytes)
        self.assertEqual(fake_tx_bytes, inspected_stats.tx_bytes)

    def test_inspect_disks(self):
        fake_instance_name = 'fake_instance_name'
        fake_read_mb = 1000
        fake_write_mb = 2000
        fake_instance_id = "fake_fake_instance_id"
        fake_host_resource = "fake_host_resource"

        fake_device = {"instance_id": fake_instance_id,
                       "host_resource": fake_host_resource}

        self._inspector._utils.get_disk_metrics.return_value = [{
            'read_mb': fake_read_mb,
            'write_mb': fake_write_mb,
            'instance_id': fake_instance_id,
            'host_resource': fake_host_resource}]

        inspected_disks = list(self._inspector.inspect_disks(
            fake_instance_name))

        self.assertEqual(1, len(inspected_disks))
        self.assertEqual(2, len(inspected_disks[0]))

        inspected_disk, inspected_stats = inspected_disks[0]

        self.assertEqual(fake_device, inspected_disk.device)

        self.assertEqual(fake_read_mb * 1024, inspected_stats.read_bytes)
        self.assertEqual(fake_write_mb * 1024, inspected_stats.write_bytes)
