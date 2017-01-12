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

import mock
from oslo_vmware import api
from oslotest import base

from ceilometer.compute.virt.vmware import vsphere_operations


class VsphereOperationsTest(base.BaseTestCase):

    def setUp(self):
        api_session = api.VMwareAPISession("test_server", "test_user",
                                           "test_password", 0, None,
                                           create_session=False)
        api_session._vim = mock.MagicMock()
        self._vsphere_ops = vsphere_operations.VsphereOperations(api_session,
                                                                 1000)
        super(VsphereOperationsTest, self).setUp()

    def test_get_vm_object(self):

        vm1_moid = "vm-1"
        vm2_moid = "vm-2"
        vm1_instance = "0a651a71-142c-4813-aaa6-42e5d5c80d85"
        vm2_instance = "db1d2533-6bef-4cb2-aef3-920e109f5693"

        def construct_mock_vm_object(vm_moid, vm_instance):
            vm_object = mock.MagicMock()
            vm_object.obj.value = vm_moid
            vm_object.obj._type = "VirtualMachine"
            vm_object.propSet[0].val = vm_instance
            return vm_object

        def retrieve_props_side_effect(pc, specSet,
                                       options, skip_op_id=False):
            # assert inputs
            self.assertEqual(self._vsphere_ops._max_objects,
                             options.maxObjects)
            self.assertEqual(vsphere_operations.VM_INSTANCE_ID_PROPERTY,
                             specSet[0].pathSet[0])

            # mock return result
            vm1 = construct_mock_vm_object(vm1_moid, vm1_instance)
            vm2 = construct_mock_vm_object(vm2_moid, vm2_instance)
            result = mock.MagicMock()
            result.objects.__iter__.return_value = [vm1, vm2]
            return result

        vim_mock = self._vsphere_ops._api_session._vim
        vim_mock.RetrievePropertiesEx.side_effect = retrieve_props_side_effect
        vim_mock.ContinueRetrievePropertiesEx.return_value = None

        vm_object = self._vsphere_ops.get_vm_mobj(vm1_instance)
        self.assertEqual(vm1_moid, vm_object.value)
        self.assertEqual("VirtualMachine", vm_object._type)

        vm_object = self._vsphere_ops.get_vm_mobj(vm2_instance)
        self.assertEqual(vm2_moid, vm_object.value)
        self.assertEqual("VirtualMachine", vm_object._type)

    def test_query_vm_property(self):
        vm_object = mock.MagicMock()
        vm_object.value = "vm-21"
        vm_property_name = "runtime.powerState"
        vm_property_val = "poweredON"

        def retrieve_props_side_effect(pc, specSet, options,
                                       skip_op_id=False):
            # assert inputs
            self.assertEqual(vm_object.value, specSet[0].obj.value)
            self.assertEqual(vm_property_name, specSet[0].pathSet[0])

            # mock return result
            result = mock.MagicMock()
            result.objects[0].propSet[0].val = vm_property_val
            return result

        vim_mock = self._vsphere_ops._api_session._vim
        vim_mock.RetrievePropertiesEx.side_effect = retrieve_props_side_effect
        actual_val = self._vsphere_ops.query_vm_property(vm_object,
                                                         vm_property_name)
        self.assertEqual(vm_property_val, actual_val)

    def test_get_perf_counter_id(self):

        def construct_mock_counter_info(group_name, counter_name, rollup_type,
                                        counter_id):
            counter_info = mock.MagicMock()
            counter_info.groupInfo.key = group_name
            counter_info.nameInfo.key = counter_name
            counter_info.rollupType = rollup_type
            counter_info.key = counter_id
            return counter_info

        def retrieve_props_side_effect(pc, specSet, options,
                                       skip_op_id=False):
            # assert inputs
            self.assertEqual(vsphere_operations.PERF_COUNTER_PROPERTY,
                             specSet[0].pathSet[0])

            # mock return result
            counter_info1 = construct_mock_counter_info("a", "b", "c", 1)
            counter_info2 = construct_mock_counter_info("x", "y", "z", 2)
            result = mock.MagicMock()
            (result.objects[0].propSet[0].val.PerfCounterInfo.__iter__.
             return_value) = [counter_info1, counter_info2]
            return result

        vim_mock = self._vsphere_ops._api_session._vim
        vim_mock.RetrievePropertiesEx.side_effect = retrieve_props_side_effect

        counter_id = self._vsphere_ops.get_perf_counter_id("a:b:c")
        self.assertEqual(1, counter_id)

        counter_id = self._vsphere_ops.get_perf_counter_id("x:y:z")
        self.assertEqual(2, counter_id)

    def test_query_vm_stats(self):

        vm_object = mock.MagicMock()
        vm_object.value = "vm-21"
        device1 = "device-1"
        device2 = "device-2"
        device3 = "device-3"
        counter_id = 5

        def construct_mock_metric_series(device_name, stat_values):
            metric_series = mock.MagicMock()
            metric_series.value = stat_values
            metric_series.id.instance = device_name
            return metric_series

        def vim_query_perf_side_effect(perf_manager, querySpec):
            # assert inputs
            self.assertEqual(vm_object.value, querySpec[0].entity.value)
            self.assertEqual(counter_id, querySpec[0].metricId[0].counterId)
            self.assertEqual(vsphere_operations.VC_REAL_TIME_SAMPLING_INTERVAL,
                             querySpec[0].intervalId)

            # mock return result
            perf_stats = mock.MagicMock()
            perf_stats[0].sampleInfo = ["s1", "s2", "s3"]
            perf_stats[0].value.__iter__.return_value = [
                construct_mock_metric_series(None, [111, 222, 333]),
                construct_mock_metric_series(device1, [100, 200, 300]),
                construct_mock_metric_series(device2, [10, 20, 30]),
                construct_mock_metric_series(device3, [1, 2, 3])
            ]
            return perf_stats

        vim_mock = self._vsphere_ops._api_session._vim
        vim_mock.QueryPerf.side_effect = vim_query_perf_side_effect
        ops = self._vsphere_ops

        # test aggregate stat
        stat_val = ops.query_vm_aggregate_stats(vm_object, counter_id, 60)
        self.assertEqual(222, stat_val)

        # test per-device(non-aggregate) stats
        expected_device_stats = {
            device1: 200,
            device2: 20,
            device3: 2
        }
        stats = ops.query_vm_device_stats(vm_object, counter_id, 60)
        self.assertEqual(expected_device_stats, stats)
