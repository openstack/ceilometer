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
"""Implementation of Inspector abstraction for Hyper-V"""

from oslo_config import cfg
from oslo_log import log
from oslo_utils import units

from ceilometer.compute.pollsters import util
from ceilometer.compute.virt.hyperv import utilsv2
from ceilometer.compute.virt import inspector as virt_inspector


CONF = cfg.CONF
LOG = log.getLogger(__name__)


class HyperVInspector(virt_inspector.Inspector):

    def __init__(self):
        super(HyperVInspector, self).__init__()
        self._utils = utilsv2.UtilsV2()

    def inspect_cpus(self, instance):
        instance_name = util.instance_name(instance)
        (cpu_clock_used,
         cpu_count, uptime) = self._utils.get_cpu_metrics(instance_name)
        host_cpu_clock, host_cpu_count = self._utils.get_host_cpu_info()

        cpu_percent_used = (cpu_clock_used /
                            float(host_cpu_clock * cpu_count))
        # Nanoseconds
        cpu_time = (int(uptime * cpu_percent_used) * units.k)

        return virt_inspector.CPUStats(number=cpu_count, time=cpu_time)

    def inspect_memory_usage(self, instance, duration=None):
        instance_name = util.instance_name(instance)
        usage = self._utils.get_memory_metrics(instance_name)
        return virt_inspector.MemoryUsageStats(usage=usage)

    def inspect_vnics(self, instance):
        instance_name = util.instance_name(instance)
        for vnic_metrics in self._utils.get_vnic_metrics(instance_name):
            interface = virt_inspector.Interface(
                name=vnic_metrics["element_name"],
                mac=vnic_metrics["address"],
                fref=None,
                parameters=None)

            stats = virt_inspector.InterfaceStats(
                rx_bytes=vnic_metrics['rx_mb'] * units.Mi,
                rx_packets=0,
                tx_bytes=vnic_metrics['tx_mb'] * units.Mi,
                tx_packets=0)

            yield (interface, stats)

    def inspect_disks(self, instance):
        instance_name = util.instance_name(instance)
        for disk_metrics in self._utils.get_disk_metrics(instance_name):
            disk = virt_inspector.Disk(device=disk_metrics['instance_id'])
            stats = virt_inspector.DiskStats(
                read_requests=0,
                # Return bytes
                read_bytes=disk_metrics['read_mb'] * units.Mi,
                write_requests=0,
                write_bytes=disk_metrics['write_mb'] * units.Mi,
                errors=0)

            yield (disk, stats)

    def inspect_disk_latency(self, instance):
        instance_name = util.instance_name(instance)
        for disk_metrics in self._utils.get_disk_latency_metrics(
                instance_name):
            disk = virt_inspector.Disk(device=disk_metrics['instance_id'])
            stats = virt_inspector.DiskLatencyStats(
                disk_latency=disk_metrics['disk_latency'])

            yield (disk, stats)

    def inspect_disk_iops(self, instance):
        instance_name = util.instance_name(instance)
        for disk_metrics in self._utils.get_disk_iops_count(instance_name):
            disk = virt_inspector.Disk(device=disk_metrics['instance_id'])
            stats = virt_inspector.DiskIOPSStats(
                iops_count=disk_metrics['iops_count'])

            yield (disk, stats)
