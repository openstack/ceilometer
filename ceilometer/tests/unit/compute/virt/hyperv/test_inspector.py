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
Tests for Hyper-V inspector.
"""

import sys

import mock
from os_win import exceptions as os_win_exc
from oslo_utils import units
from oslotest import base

from ceilometer.compute.virt.hyperv import inspector as hyperv_inspector
from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer import service


class TestHyperVInspection(base.BaseTestCase):

    @mock.patch.object(hyperv_inspector, 'utilsfactory', mock.MagicMock())
    @mock.patch.object(hyperv_inspector.HyperVInspector,
                       '_compute_host_max_cpu_clock')
    def setUp(self, mock_compute_host_cpu_clock):
        conf = service.prepare_service([], [])
        self._inspector = hyperv_inspector.HyperVInspector(conf)
        self._inspector._utils = mock.MagicMock()

        super(TestHyperVInspection, self).setUp()

    def test_converted_exception(self):
        self._inspector._utils.get_cpu_metrics.side_effect = (
            os_win_exc.OSWinException)
        self.assertRaises(virt_inspector.InspectorException,
                          self._inspector.inspect_instance,
                          mock.sentinel.instance, None)

        self._inspector._utils.get_cpu_metrics.side_effect = (
            os_win_exc.HyperVException)
        self.assertRaises(virt_inspector.InspectorException,
                          self._inspector.inspect_instance,
                          mock.sentinel.instance, None)

        self._inspector._utils.get_cpu_metrics.side_effect = (
            os_win_exc.NotFound(resource='foofoo'))
        self.assertRaises(virt_inspector.InstanceNotFoundException,
                          self._inspector.inspect_instance,
                          mock.sentinel.instance, None)

    def test_assert_original_traceback_maintained(self):
        def bar(self):
            foo = "foofoo"
            raise os_win_exc.NotFound(resource=foo)

        self._inspector._utils.get_cpu_metrics.side_effect = bar
        try:
            self._inspector.inspect_instance(mock.sentinel.instance, None)
            self.fail("Test expected exception, but it was not raised.")
        except virt_inspector.InstanceNotFoundException:
            # exception has been raised as expected.
            _, _, trace = sys.exc_info()
            while trace.tb_next:
                # iterate until the original exception source, bar.
                trace = trace.tb_next

            # original frame will contain the 'foo' variable.
            self.assertEqual('foofoo', trace.tb_frame.f_locals['foo'])

    @mock.patch.object(hyperv_inspector, 'utilsfactory')
    def test_compute_host_max_cpu_clock(self, mock_utilsfactory):
        mock_cpu = {'MaxClockSpeed': 1000}
        hostutils = mock_utilsfactory.get_hostutils.return_value.get_cpus_info
        hostutils.return_value = [mock_cpu, mock_cpu]

        cpu_clock = self._inspector._compute_host_max_cpu_clock()
        self.assertEqual(2000.0, cpu_clock)

    def test_inspect_instance(self):
        fake_instance_name = 'fake_instance_name'
        fake_cpu_clock_used = 2000
        fake_cpu_count = 3000
        fake_uptime = 4000

        self._inspector._host_max_cpu_clock = 4000.0
        fake_cpu_percent_used = (fake_cpu_clock_used /
                                 self._inspector._host_max_cpu_clock)
        fake_cpu_time = (int(fake_uptime * fake_cpu_percent_used) *
                         1000)
        self._inspector._utils.get_cpu_metrics.return_value = (
            fake_cpu_clock_used, fake_cpu_count, fake_uptime)
        fake_usage = self._inspector._utils.get_memory_metrics.return_value

        stats = self._inspector.inspect_instance(fake_instance_name, None)

        self.assertEqual(fake_cpu_count, stats.cpu_number)
        self.assertEqual(fake_cpu_time, stats.cpu_time)
        self.assertEqual(fake_usage, stats.memory_usage)

    def test_inspect_vnics(self):
        fake_instance_name = 'fake_instance_name'
        fake_rx_mb = 1000
        fake_tx_mb = 2000
        fake_element_name = 'fake_element_name'
        fake_address = 'fake_address'

        self._inspector._utils.get_vnic_metrics.return_value = [{
            'rx_mb': fake_rx_mb,
            'tx_mb': fake_tx_mb,
            'element_name': fake_element_name,
            'address': fake_address}]

        inspected_vnics = list(self._inspector.inspect_vnics(
            fake_instance_name, None))

        self.assertEqual(1, len(inspected_vnics))

        inspected_stats = inspected_vnics[0]
        self.assertEqual(fake_element_name, inspected_stats.name)
        self.assertEqual(fake_address, inspected_stats.mac)
        self.assertEqual(fake_rx_mb * units.Mi, inspected_stats.rx_bytes)
        self.assertEqual(fake_tx_mb * units.Mi, inspected_stats.tx_bytes)

    def test_inspect_disks(self):
        fake_instance_name = 'fake_instance_name'
        fake_read_mb = 1000
        fake_write_mb = 2000
        fake_instance_id = "fake_fake_instance_id"
        fake_host_resource = "fake_host_resource"

        self._inspector._utils.get_disk_metrics.return_value = [{
            'read_mb': fake_read_mb,
            'write_mb': fake_write_mb,
            'instance_id': fake_instance_id,
            'host_resource': fake_host_resource}]

        inspected_disks = list(self._inspector.inspect_disks(
            fake_instance_name, None))

        self.assertEqual(1, len(inspected_disks))

        inspected_stats = inspected_disks[0]
        self.assertEqual(fake_instance_id, inspected_stats.device)
        self.assertEqual(fake_read_mb * units.Mi, inspected_stats.read_bytes)
        self.assertEqual(fake_write_mb * units.Mi, inspected_stats.write_bytes)

    def test_inspect_disk_latency(self):
        fake_instance_name = mock.sentinel.INSTANCE_NAME
        fake_disk_latency = 1000
        fake_instance_id = mock.sentinel.INSTANCE_ID

        self._inspector._utils.get_disk_latency_metrics.return_value = [{
            'disk_latency': fake_disk_latency,
            'instance_id': fake_instance_id}]

        inspected_disks = list(self._inspector.inspect_disk_latency(
            fake_instance_name, None))

        self.assertEqual(1, len(inspected_disks))

        inspected_stats = inspected_disks[0]
        self.assertEqual(fake_instance_id, inspected_stats.device)
        self.assertEqual(1, inspected_stats.disk_latency)

    def test_inspect_disk_iops_count(self):
        fake_instance_name = mock.sentinel.INSTANCE_NAME
        fake_disk_iops_count = 53
        fake_instance_id = mock.sentinel.INSTANCE_ID

        self._inspector._utils.get_disk_iops_count.return_value = [{
            'iops_count': fake_disk_iops_count,
            'instance_id': fake_instance_id}]

        inspected_disks = list(self._inspector.inspect_disk_iops(
            fake_instance_name, None))

        self.assertEqual(1, len(inspected_disks))

        inspected_stats = inspected_disks[0]
        self.assertEqual(fake_instance_id, inspected_stats.device)
        self.assertEqual(53, inspected_stats.iops_count)
