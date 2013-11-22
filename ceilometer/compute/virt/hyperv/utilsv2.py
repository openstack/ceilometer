# Copyright 2013 Cloudbase Solutions Srl
#
# Author: Claudiu Belu <cbelu@cloudbasesolutions.com>
#         Alessandro Pilotti <apilotti@cloudbasesolutions.com>
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
Utility class for VM related operations.
Based on the "root/virtualization/v2" namespace available starting with
Hyper-V Server / Windows Server 2012.
"""

import sys

if sys.platform == 'win32':
    import wmi

from oslo.config import cfg

from ceilometer.compute.virt import inspector
from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log as logging

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class HyperVException(inspector.InspectorException):
    pass


class UtilsV2(object):

    _VIRTUAL_SYSTEM_TYPE_REALIZED = 'Microsoft:Hyper-V:System:Realized'

    _PROC_SETTING = 'Msvm_ProcessorSettingData'
    _SYNTH_ETH_PORT = 'Msvm_SyntheticEthernetPortSettingData'
    _ETH_PORT_ALLOC = 'Msvm_EthernetPortAllocationSettingData'
    _STORAGE_ALLOC = 'Msvm_StorageAllocationSettingData'
    _VS_SETTING_DATA = 'Msvm_VirtualSystemSettingData'
    _AGGREG_METRIC = 'Msvm_AggregationMetricDefinition'
    _METRICS_ME = 'Msvm_MetricForME'

    _CPU_METRIC_NAME = 'Aggregated Average CPU Utilization'
    _NET_IN_METRIC_NAME = 'Aggregated Filtered Incoming Network Traffic'
    _NET_OUT_METRIC_NAME = 'Aggregated Filtered Outgoing Network Traffic'
    # Disk metrics are supported from Hyper-V 2012 R2
    _DISK_RD_METRIC_NAME = 'Disk Data Read'
    _DISK_WR_METRIC_NAME = 'Disk Data Written'

    def __init__(self, host='.'):
        if sys.platform == 'win32':
            self._init_hyperv_wmi_conn(host)
            self._init_cimv2_wmi_conn(host)
        self._host_cpu_info = None

    def _init_hyperv_wmi_conn(self, host):
        self._conn = wmi.WMI(moniker='//%s/root/virtualization/v2' % host)

    def _init_cimv2_wmi_conn(self, host):
        self._conn_cimv2 = wmi.WMI(moniker='//%s/root/cimv2' % host)

    def get_host_cpu_info(self):
        if not self._host_cpu_info:
            host_cpus = self._conn_cimv2.Win32_Processor()
            self._host_cpu_info = (host_cpus[0].MaxClockSpeed, len(host_cpus))
        return self._host_cpu_info

    def get_all_vms(self):
        vms = [(v.ElementName, v.Name) for v in
               self._conn.Msvm_ComputerSystem(['ElementName', 'Name'],
                                              Caption="Virtual Machine")]
        return vms

    def get_cpu_metrics(self, vm_name):
        vm = self._lookup_vm(vm_name)
        cpu_sd = self._get_vm_resources(vm, self._PROC_SETTING)[0]
        cpu_metrics_def = self._get_metric_def(self._CPU_METRIC_NAME)
        cpu_metric_aggr = self._get_metrics(vm, cpu_metrics_def)

        cpu_used = 0
        if cpu_metric_aggr:
            cpu_used = long(cpu_metric_aggr[0].MetricValue)

        return (cpu_used,
                int(cpu_sd.VirtualQuantity),
                long(vm.OnTimeInMilliseconds))

    def get_vnic_metrics(self, vm_name):
        vm = self._lookup_vm(vm_name)
        ports = self._get_vm_resources(vm, self._ETH_PORT_ALLOC)
        vnics = self._get_vm_resources(vm, self._SYNTH_ETH_PORT)

        metric_def_in = self._get_metric_def(self._NET_IN_METRIC_NAME)
        metric_def_out = self._get_metric_def(self._NET_OUT_METRIC_NAME)

        for port in ports:
            vnic = [v for v in vnics if port.Parent == v.path_()][0]
            metric_values = self._get_metric_values(
                port, [metric_def_in, metric_def_out])

            yield {
                'rx_bytes': metric_values[0],
                'tx_bytes': metric_values[1],
                'element_name': vnic.ElementName,
                'address': vnic.Address
            }

    def get_disk_metrics(self, vm_name):
        vm = self._lookup_vm(vm_name)
        metric_def_r = self._get_metric_def(self._DISK_RD_METRIC_NAME)
        metric_def_w = self._get_metric_def(self._DISK_WR_METRIC_NAME)

        disks = self._get_vm_resources(vm, self._STORAGE_ALLOC)
        for disk in disks:
            metric_values = self._get_metric_values(
                disk, [metric_def_r, metric_def_w])

            # Thi sis e.g. the VHD file location
            if disk.HostResource:
                host_resource = disk.HostResource[0]

            yield {
                # Values are in megabytes
                'read_mb': metric_values[0],
                'write_mb': metric_values[1],
                'instance_id': disk.InstanceID,
                'host_resource': host_resource
            }

    def _sum_metric_values(self, metrics):
        tot_metric_val = 0
        for metric in metrics:
            tot_metric_val += long(metric.MetricValue)
        return tot_metric_val

    def _get_metric_values(self, element, metric_defs):
        element_metrics = element.associators(
            wmi_association_class=self._METRICS_ME)

        metric_values = []
        for metric_def in metric_defs:
            if metric_def:
                metrics = self._filter_metrics(element_metrics, metric_def)
                metric_values.append(self._sum_metric_values(metrics))
            else:
                # In case the metric is not defined on this host
                metric_values.append(0)
        return metric_values

    def _lookup_vm(self, vm_name):
        vms = self._conn.Msvm_ComputerSystem(ElementName=vm_name)
        n = len(vms)
        if n == 0:
            raise inspector.InstanceNotFoundException(
                _('VM %s not found on Hyper-V') % vm_name)
        elif n > 1:
            raise HyperVException(_('Duplicate VM name found: %s') % vm_name)
        else:
            return vms[0]

    def _get_metrics(self, element, metric_def):
        return self._filter_metrics(
            element.associators(
                wmi_association_class=self._METRICS_ME), metric_def)

    def _filter_metrics(self, all_metrics, metric_def):
        return [v for v in all_metrics if
                v.MetricDefinitionId == metric_def.Id]

    def _get_metric_def(self, metric_def):
        metric = self._conn.CIM_BaseMetricDefinition(ElementName=metric_def)
        if metric:
            return metric[0]

    def _get_vm_setting_data(self, vm):
        vm_settings = vm.associators(
            wmi_result_class=self._VS_SETTING_DATA)
        # Avoid snapshots
        return [s for s in vm_settings if
                s.VirtualSystemType == self._VIRTUAL_SYSTEM_TYPE_REALIZED][0]

    def _get_vm_resources(self, vm, resource_class):
        setting_data = self._get_vm_setting_data(vm)
        return setting_data.associators(wmi_result_class=resource_class)
