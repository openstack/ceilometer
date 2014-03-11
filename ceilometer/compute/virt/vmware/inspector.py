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

    def inspect_vnics(self, instance_name):
        raise NotImplementedError()

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
        #Stat provided from VMware Vsphere is in Bytes, converting it to MB.
        memory = memory / (units.Mi)
        return virt_inspector.MemoryUsageStats(usage=memory)
