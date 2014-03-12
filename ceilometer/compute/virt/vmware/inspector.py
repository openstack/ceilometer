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

"""Implementation of Inspector abstraction for VMware vSphere"""

from oslo.config import cfg
from oslo.vmware import api
from oslo.vmware import vim

from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.compute.virt.vmware import vsphere_operations
from ceilometer.openstack.common import units


opt_group = cfg.OptGroup(name='vmware',
                         title='Options for VMware')

OPTS = [
    cfg.StrOpt('host_ip',
               default='',
               help='IP address of the VMware Vsphere host'),
    cfg.StrOpt('host_username',
               default='',
               help='Username of VMware Vsphere'),
    cfg.StrOpt('host_password',
               default='',
               help='Password of VMware Vsphere'),
    cfg.IntOpt('api_retry_count',
               default=10,
               help='Number of times a VMware Vsphere API must be retried'),
    cfg.FloatOpt('task_poll_interval',
                 default=0.5,
                 help='Sleep time in seconds for polling an ongoing async '
                 'task'),
]

cfg.CONF.register_group(opt_group)
cfg.CONF.register_opts(OPTS, group=opt_group)

VC_AVERAGE_MEMORY_CONSUMED_CNTR = 'mem:consumed:average'
VC_AVERAGE_CPU_CONSUMED_CNTR = 'cpu:usage:average'
VC_NETWORK_RX_BYTES_COUNTER = 'net:bytesRx:average'
VC_NETWORK_TX_BYTES_COUNTER = 'net:bytesTx:average'
VC_DISK_READ_RATE_CNTR = "disk:read:average"
VC_DISK_READ_REQUESTS_RATE_CNTR = "disk:numberReadAveraged:average"
VC_DISK_WRITE_RATE_CNTR = "disk:write:average"
VC_DISK_WRITE_REQUESTS_RATE_CNTR = "disk:numberWriteAveraged:average"


def get_api_session():
    hostIp = cfg.CONF.vmware.host_ip
    wsdl_loc = vim.Vim._get_wsdl_loc("https", hostIp)
    api_session = api.VMwareAPISession(
        hostIp,
        cfg.CONF.vmware.host_username,
        cfg.CONF.vmware.host_password,
        cfg.CONF.vmware.api_retry_count,
        cfg.CONF.vmware.task_poll_interval,
        wsdl_loc=wsdl_loc)
    return api_session


class VsphereInspector(virt_inspector.Inspector):

    def __init__(self):
        super(VsphereInspector, self).__init__()
        self._ops = vsphere_operations.VsphereOperations(
            get_api_session(), 1000)

    def inspect_instances(self):
        raise NotImplementedError()

    def inspect_cpus(self, instance_name):
        raise NotImplementedError()

    def inspect_cpu_util(self, instance):
        vm_moid = self._ops.get_vm_moid(instance.id)
        if vm_moid is None:
            raise virt_inspector.InstanceNotFoundException(
                _('VM %s not found in VMware Vsphere') % instance.id)
        cpu_util_counter_id = self._ops.get_perf_counter_id(
            VC_AVERAGE_CPU_CONSUMED_CNTR)
        cpu_util = self._ops.query_vm_aggregate_stats(vm_moid,
                                                      cpu_util_counter_id)
        return virt_inspector.CPUUtilStats(util=cpu_util)

    def inspect_vnics(self, instance_name):
        raise NotImplementedError()

    def inspect_vnic_rates(self, instance):
        vm_moid = self._ops.get_vm_moid(instance.id)
        if not vm_moid:
            raise virt_inspector.InstanceNotFoundException(
                _('VM %s not found in VMware Vsphere') % instance.id)

        vnic_stats = {}
        vnic_ids = set()

        for net_counter in (VC_NETWORK_RX_BYTES_COUNTER,
                            VC_NETWORK_TX_BYTES_COUNTER):
            net_counter_id = self._ops.get_perf_counter_id(net_counter)
            vnic_id_to_stats_map = \
                self._ops.query_vm_device_stats(vm_moid, net_counter_id)
            vnic_stats[net_counter] = vnic_id_to_stats_map
            vnic_ids.update(vnic_id_to_stats_map.iterkeys())

        for vnic_id in vnic_ids:
            rx_bytes_rate = (vnic_stats[VC_NETWORK_RX_BYTES_COUNTER]
                             .get(vnic_id, 0) / units.k)
            tx_bytes_rate = (vnic_stats[VC_NETWORK_TX_BYTES_COUNTER]
                             .get(vnic_id, 0) / units.k)

            stats = virt_inspector.InterfaceRateStats(rx_bytes_rate,
                                                      tx_bytes_rate)
            interface = virt_inspector.Interface(
                name=vnic_id,
                mac=None,
                fref=None,
                parameters=None)
            yield (interface, stats)

    def inspect_disks(self, instance_name):
        raise NotImplementedError()

    def inspect_memory_usage(self, instance):
        vm_moid = self._ops.get_vm_moid(instance.id)
        if vm_moid is None:
            raise virt_inspector.InstanceNotFoundException(
                _('VM %s not found in VMware Vsphere') % instance.id)
        mem_counter_id = self._ops.get_perf_counter_id(
            VC_AVERAGE_MEMORY_CONSUMED_CNTR)
        memory = self._ops.query_vm_aggregate_stats(vm_moid, mem_counter_id)
        # Stat provided from VMware Vsphere is in Bytes, converting it to MB.
        memory = memory / (units.Mi)
        return virt_inspector.MemoryUsageStats(usage=memory)

    def inspect_disk_rates(self, instance):
        vm_moid = self._ops.get_vm_moid(instance.id)
        if not vm_moid:
            raise virt_inspector.InstanceNotFoundException(
                _('VM %s not found in VMware Vsphere') % instance.id)

        disk_stats = {}
        disk_ids = set()
        disk_counters = [
            VC_DISK_READ_RATE_CNTR,
            VC_DISK_READ_REQUESTS_RATE_CNTR,
            VC_DISK_WRITE_RATE_CNTR,
            VC_DISK_WRITE_REQUESTS_RATE_CNTR
        ]

        for disk_counter in disk_counters:
            disk_counter_id = self._ops.get_perf_counter_id(disk_counter)
            disk_id_to_stat_map = self._ops.query_vm_device_stats(
                vm_moid, disk_counter_id)
            disk_stats[disk_counter] = disk_id_to_stat_map
            disk_ids.update(disk_id_to_stat_map.iterkeys())

        for disk_id in disk_ids:

            def stat_val(counter_name):
                return disk_stats[counter_name].get(disk_id, 0)

            disk = virt_inspector.Disk(device=disk_id)
            disk_rate_info = virt_inspector.DiskRateStats(
                read_bytes_rate=stat_val(VC_DISK_READ_RATE_CNTR) * units.Ki,
                read_requests_rate=stat_val(VC_DISK_READ_REQUESTS_RATE_CNTR),
                write_bytes_rate=stat_val(VC_DISK_WRITE_RATE_CNTR) * units.Ki,
                write_requests_rate=stat_val(VC_DISK_WRITE_REQUESTS_RATE_CNTR)
            )
            yield(disk, disk_rate_info)
