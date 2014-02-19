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
"""Implementation of Inspector abstraction for Hyper-V"""

from oslo.config import cfg

from ceilometer.compute.virt.hyperv import utilsv2
from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.openstack.common import log
from ceilometer.openstack.common import units

CONF = cfg.CONF
LOG = log.getLogger(__name__)


class HyperVInspector(virt_inspector.Inspector):

    def __init__(self):
        super(HyperVInspector, self).__init__()
        self._utils = utilsv2.UtilsV2()

    def inspect_instances(self):
        for element_name, name in self._utils.get_all_vms():
            yield virt_inspector.Instance(
                name=element_name,
                UUID=name)

    def inspect_cpus(self, instance_name):
        (cpu_clock_used,
         cpu_count, uptime) = self._utils.get_cpu_metrics(instance_name)
        host_cpu_clock, host_cpu_count = self._utils.get_host_cpu_info()

        cpu_percent_used = (cpu_clock_used /
                            float(host_cpu_clock * cpu_count))
        # Nanoseconds
        cpu_time = (long(uptime * cpu_percent_used) * units.k)

        return virt_inspector.CPUStats(number=cpu_count, time=cpu_time)

    def inspect_vnics(self, instance_name):
        for vnic_metrics in self._utils.get_vnic_metrics(instance_name):
            interface = virt_inspector.Interface(
                name=vnic_metrics["element_name"],
                mac=vnic_metrics["address"],
                fref=None,
                parameters=None)

            stats = virt_inspector.InterfaceStats(
                rx_bytes=vnic_metrics['rx_bytes'],
                rx_packets=0,
                tx_bytes=vnic_metrics['tx_bytes'],
                tx_packets=0)

            yield (interface, stats)

    def inspect_disks(self, instance_name):
        for disk_metrics in self._utils.get_disk_metrics(instance_name):
            device = dict([(i, disk_metrics[i])
                          for i in ['instance_id', 'host_resource']
                          if i in disk_metrics])

            disk = virt_inspector.Disk(device=device)
            stats = virt_inspector.DiskStats(
                read_requests=0,
                # Return bytes
                read_bytes=disk_metrics['read_mb'] * units.Ki,
                write_requests=0,
                write_bytes=disk_metrics['write_mb'] * units.Ki,
                errors=0)

            yield (disk, stats)
