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
Tests for VMware Vsphere inspector.
"""

import mock

from oslo.vmware import api

from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.compute.virt.vmware import inspector as vsphere_inspector
from ceilometer.openstack.common import test


class TestVsphereInspection(test.BaseTestCase):

    def setUp(self):
        api_session = api.VMwareAPISession("test_server", "test_user",
                                           "test_password", 0, None,
                                           create_session=False)
        api_session._vim = mock.MagicMock()
        vsphere_inspector.get_api_session = mock.Mock(
            return_value=api_session)
        self._inspector = vsphere_inspector.VsphereInspector()
        self._inspector._ops = mock.MagicMock()

        super(TestVsphereInspection, self).setUp()

    def test_inspect_memory_usage(self):
        fake_instance_moid = 'fake_instance_moid'
        fake_instance_id = 'fake_instance_id'
        fake_perf_counter_id = 'fake_perf_counter_id'
        fake_memory_value = 1048576.0
        fake_stat = virt_inspector.MemoryUsageStats(usage=1.0)

        def construct_mock_instance_object(fake_instance_id):
            instance_object = mock.MagicMock()
            instance_object.id = fake_instance_id
            return instance_object

        fake_instance = construct_mock_instance_object(fake_instance_id)
        self._inspector._ops.get_vm_moid.return_value = fake_instance_moid
        self._inspector._ops.get_perf_counter_id.return_value = \
            fake_perf_counter_id
        self._inspector._ops.query_vm_aggregate_stats.return_value = \
            fake_memory_value
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
        self._inspector._ops.get_perf_counter_id.return_value = \
            fake_perf_counter_id
        self._inspector._ops.query_vm_aggregate_stats.return_value = \
            fake_cpu_util_value
        cpu_util_stat = self._inspector.inspect_cpu_util(fake_instance)
        self.assertEqual(fake_stat, cpu_util_stat)
