#
# Copyright 2012 eNovance <licensing@enovance.com>
# Copyright 2012 Red Hat, Inc
# Copyright 2014 Cisco Systems, Inc
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
from ceilometer.compute import pollsters
from ceilometer import sample


class PerDeviceDiskPollster(pollsters.GenericComputePollster):
    inspector_method = "inspect_disks"

    @staticmethod
    def get_resource_id(instance, stats):
        return "%s-%s" % (instance.id, stats.device)

    @staticmethod
    def get_additional_metadata(instance, stats):
        return {'disk_name': stats.device}


class PerDeviceReadRequestsPollster(PerDeviceDiskPollster):
    sample_name = 'disk.device.read.requests'
    sample_unit = 'request'
    sample_type = sample.TYPE_CUMULATIVE
    sample_stats_key = 'read_requests'


class PerDeviceReadBytesPollster(PerDeviceDiskPollster):
    sample_name = 'disk.device.read.bytes'
    sample_unit = 'B'
    sample_type = sample.TYPE_CUMULATIVE
    sample_stats_key = 'read_bytes'


class PerDeviceWriteRequestsPollster(PerDeviceDiskPollster):
    sample_name = 'disk.device.write.requests'
    sample_unit = 'request'
    sample_type = sample.TYPE_CUMULATIVE
    sample_stats_key = 'write_requests'


class PerDeviceWriteBytesPollster(PerDeviceDiskPollster):
    sample_name = 'disk.device.write.bytes'
    sample_unit = 'B'
    sample_type = sample.TYPE_CUMULATIVE
    sample_stats_key = 'write_bytes'


class PerDeviceDiskLatencyPollster(PerDeviceDiskPollster):
    inspector_method = 'inspect_disk_latency'
    sample_name = 'disk.device.latency'
    sample_unit = 'ms'
    sample_stats_key = 'disk_latency'


class PerDeviceDiskIOPSPollster(PerDeviceDiskPollster):
    inspector_method = 'inspect_disk_iops'
    sample_name = 'disk.device.iops'
    sample_unit = 'count/s'
    sample_stats_key = 'iops_count'


class PerDeviceCapacityPollster(PerDeviceDiskPollster):
    inspector_method = 'inspect_disk_info'
    sample_name = 'disk.device.capacity'
    sample_unit = 'B'
    sample_stats_key = 'capacity'


class PerDeviceAllocationPollster(PerDeviceDiskPollster):
    inspector_method = 'inspect_disk_info'
    sample_name = 'disk.device.allocation'
    sample_unit = 'B'
    sample_stats_key = 'allocation'


class PerDevicePhysicalPollster(PerDeviceDiskPollster):
    inspector_method = 'inspect_disk_info'
    sample_name = 'disk.device.usage'
    sample_unit = 'B'
    sample_stats_key = 'physical'


class PerDeviceDiskReadLatencyPollster(PerDeviceDiskPollster):
    sample_name = 'disk.device.read.latency'
    sample_type = sample.TYPE_CUMULATIVE
    sample_unit = 'ns'
    sample_stats_key = 'rd_total_times'


class PerDeviceDiskWriteLatencyPollster(PerDeviceDiskPollster):
    sample_name = 'disk.device.write.latency'
    sample_type = sample.TYPE_CUMULATIVE
    sample_unit = 'ns'
    sample_stats_key = 'wr_total_times'
