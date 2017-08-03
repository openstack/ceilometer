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

try:
    from oslo_vmware import vim_util
except ImportError:
    # NOTE(sileht): this is safe because inspector will not load
    vim_util = None


PERF_MANAGER_TYPE = "PerformanceManager"
PERF_COUNTER_PROPERTY = "perfCounter"
VM_INSTANCE_ID_PROPERTY = 'config.extraConfig["nvp.vm-uuid"].value'

# ESXi Servers sample performance data every 20 seconds. 20-second interval
# data is called instance data or real-time data. To retrieve instance data,
# we need to specify a value of 20 seconds for the "PerfQuerySpec.intervalId"
# property. In that case the "QueryPerf" method operates as a raw data feed
# that bypasses the vCenter database and instead retrieves performance data
# from an ESXi host.
# The following value is time interval for real-time performance stats
# in seconds and it is not configurable.
VC_REAL_TIME_SAMPLING_INTERVAL = 20


class VsphereOperations(object):
    """Class to invoke vSphere APIs calls.

    vSphere APIs calls are required by various pollsters, collecting data from
    VMware infrastructure.
    """
    def __init__(self, api_session, max_objects):
        self._api_session = api_session
        self._max_objects = max_objects
        # Mapping between "VM's Nova instance Id" -> "VM's managed object"
        # In case a VM is deployed by Nova, then its name is instance ID.
        # So this map essentially has VM names as keys.
        self._vm_mobj_lookup_map = {}

        # Mapping from full name -> ID, for VC Performance counters
        self._perf_counter_id_lookup_map = None

    def _init_vm_mobj_lookup_map(self):
        session = self._api_session
        result = session.invoke_api(vim_util, "get_objects", session.vim,
                                    "VirtualMachine", self._max_objects,
                                    [VM_INSTANCE_ID_PROPERTY],
                                    False)
        while result:
            for object in result.objects:
                vm_mobj = object.obj
                # propSet will be set only if the server provides value
                if hasattr(object, 'propSet') and object.propSet:
                    vm_instance_id = object.propSet[0].val
                    if vm_instance_id:
                        self._vm_mobj_lookup_map[vm_instance_id] = vm_mobj

            result = session.invoke_api(vim_util, "continue_retrieval",
                                        session.vim, result)

    def get_vm_mobj(self, vm_instance_id):
        """Method returns VC mobj of the VM by its NOVA instance ID."""
        if vm_instance_id not in self._vm_mobj_lookup_map:
            self._init_vm_mobj_lookup_map()

        return self._vm_mobj_lookup_map.get(vm_instance_id, None)

    def _init_perf_counter_id_lookup_map(self):

        # Query details of all the performance counters from VC
        session = self._api_session
        client_factory = session.vim.client.factory
        perf_manager = session.vim.service_content.perfManager

        prop_spec = vim_util.build_property_spec(
            client_factory, PERF_MANAGER_TYPE, [PERF_COUNTER_PROPERTY])

        obj_spec = vim_util.build_object_spec(
            client_factory, perf_manager, None)

        filter_spec = vim_util.build_property_filter_spec(
            client_factory, [prop_spec], [obj_spec])

        options = client_factory.create('ns0:RetrieveOptions')
        options.maxObjects = 1

        prop_collector = session.vim.service_content.propertyCollector
        result = session.invoke_api(session.vim, "RetrievePropertiesEx",
                                    prop_collector, specSet=[filter_spec],
                                    options=options)

        perf_counter_infos = result.objects[0].propSet[0].val.PerfCounterInfo

        # Extract the counter Id for each counter and populate the map
        self._perf_counter_id_lookup_map = {}
        for perf_counter_info in perf_counter_infos:

            counter_group = perf_counter_info.groupInfo.key
            counter_name = perf_counter_info.nameInfo.key
            counter_rollup_type = perf_counter_info.rollupType
            counter_id = perf_counter_info.key

            counter_full_name = (counter_group + ":" + counter_name + ":" +
                                 counter_rollup_type)
            self._perf_counter_id_lookup_map[counter_full_name] = counter_id

    def get_perf_counter_id(self, counter_full_name):
        """Method returns the ID of VC performance counter by its full name.

        A VC performance counter is uniquely identified by the
        tuple {'Group Name', 'Counter Name', 'Rollup Type'}.
        It will have an id - counter ID (changes from one VC to another),
        which is required to query performance stats from that VC.
        This method returns the ID for a counter,
        assuming 'CounterFullName' => 'Group Name:CounterName:RollupType'.
        """
        if not self._perf_counter_id_lookup_map:
            self._init_perf_counter_id_lookup_map()
        return self._perf_counter_id_lookup_map[counter_full_name]

    # TODO(akhils@vmware.com) Move this method to common library
    # when it gets checked-in
    def query_vm_property(self, vm_mobj, property_name):
        """Method returns the value of specified property for a VM.

        :param vm_mobj: managed object of the VM whose property is to be
            queried
        :param property_name: path of the property
        """
        session = self._api_session
        return session.invoke_api(vim_util, "get_object_property",
                                  session.vim, vm_mobj, property_name)

    def query_vm_aggregate_stats(self, vm_mobj, counter_id, duration):
        """Method queries the aggregated real-time stat value for a VM.

        This method should be used for aggregate counters.

        :param vm_mobj: managed object of the VM
        :param counter_id: id of the perf counter in VC
        :param duration: in seconds from current time,
            over which the stat value was applicable
        :return: the aggregated stats value for the counter
        """
        # For aggregate counters, device_name should be ""
        stats = self._query_vm_perf_stats(vm_mobj, counter_id, "", duration)

        # Performance manager provides the aggregated stats value
        # with device name -> None
        return stats.get(None, 0)

    def query_vm_device_stats(self, vm_mobj, counter_id, duration):
        """Method queries the real-time stat values for a VM, for all devices.

        This method should be used for device(non-aggregate) counters.

        :param vm_mobj: managed object of the VM
        :param counter_id: id of the perf counter in VC
        :param duration: in seconds from current time,
            over which the stat value was applicable
        :return: a map containing the stat values keyed by the device ID/name
        """
        # For device counters, device_name should be "*" to get stat values
        # for all devices.
        stats = self._query_vm_perf_stats(vm_mobj, counter_id, "*", duration)

        # For some device counters, in addition to the per device value
        # the Performance manager also returns the aggregated value.
        # Just to be consistent, deleting the aggregated value if present.
        stats.pop(None, None)
        return stats

    def _query_vm_perf_stats(self, vm_mobj, counter_id, device_name, duration):
        """Method queries the real-time stat values for a VM.

        :param vm_mobj: managed object of the VM for which stats are needed
        :param counter_id: id of the perf counter in VC
        :param device_name: name of the device for which stats are to be
            queried. For aggregate counters pass empty string ("").
            For device counters pass "*", if stats are required over all
            devices.
        :param duration: in seconds from current time,
            over which the stat value was applicable
        :return: a map containing the stat values keyed by the device ID/name
        """

        session = self._api_session
        client_factory = session.vim.client.factory

        # Construct the QuerySpec
        metric_id = client_factory.create('ns0:PerfMetricId')
        metric_id.counterId = counter_id
        metric_id.instance = device_name

        query_spec = client_factory.create('ns0:PerfQuerySpec')
        query_spec.entity = vm_mobj
        query_spec.metricId = [metric_id]
        query_spec.intervalId = VC_REAL_TIME_SAMPLING_INTERVAL
        # We query all samples which are applicable over the specified duration
        samples_cnt = (int(duration / VC_REAL_TIME_SAMPLING_INTERVAL)
                       if duration and
                       duration >= VC_REAL_TIME_SAMPLING_INTERVAL else 1)
        query_spec.maxSample = samples_cnt

        perf_manager = session.vim.service_content.perfManager
        perf_stats = session.invoke_api(session.vim, 'QueryPerf', perf_manager,
                                        querySpec=[query_spec])

        stat_values = {}
        if perf_stats:
            entity_metric = perf_stats[0]
            sample_infos = entity_metric.sampleInfo

            if len(sample_infos) > 0:
                for metric_series in entity_metric.value:
                    # Take the average of all samples to improve the accuracy
                    # of the stat value and ignore -1 (bug 1639114)
                    filtered = [i for i in metric_series.value if i != -1]
                    stat_value = float(sum(filtered)) / len(filtered)
                    device_id = metric_series.id.instance
                    stat_values[device_id] = stat_value

        return stat_values
