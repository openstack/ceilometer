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
import collections

from oslo_log import log

from ceilometer.compute import pollsters
from ceilometer import sample

LOG = log.getLogger(__name__)


class AggregateDiskPollster(pollsters.GenericComputePollster):
    inspector_method = "inspect_disks"

    def aggregate_method(self, result):
        fields = list(result[0]._fields)
        fields.remove("device")
        agg_stats = collections.defaultdict(int)
        devices = []
        for stats in result:
            devices.append(stats.device)
            for f in fields:
                agg_stats[f] += getattr(stats, f)
        kwargs = dict(agg_stats)
        kwargs["device"] = devices
        return [result[0].__class__(**kwargs)]

    @staticmethod
    def get_additional_metadata(instance, stats):
        return {'device': stats.device}


class PerDeviceDiskPollster(pollsters.GenericComputePollster):
    inspector_method = "inspect_disks"

    @staticmethod
    def get_resource_id(instance, stats):
        return "%s-%s" % (instance.id, stats.device)

    @staticmethod
    def get_additional_metadata(instance, stats):
        return {'disk_name': stats.device}


class ReadRequestsPollster(AggregateDiskPollster):
    sample_name = 'disk.read.requests'
    sample_unit = 'request'
    sample_type = sample.TYPE_CUMULATIVE
    sample_stats_key = 'read_requests'


class PerDeviceReadRequestsPollster(PerDeviceDiskPollster):
    sample_name = 'disk.device.read.requests'
    sample_unit = 'request'
    sample_type = sample.TYPE_CUMULATIVE
    sample_stats_key = 'read_requests'


class ReadBytesPollster(AggregateDiskPollster):
    sample_name = 'disk.read.bytes'
    sample_unit = 'B'
    sample_type = sample.TYPE_CUMULATIVE
    sample_stats_key = 'read_bytes'


class PerDeviceReadBytesPollster(PerDeviceDiskPollster):
    sample_name = 'disk.device.read.bytes'
    sample_unit = 'B'
    sample_type = sample.TYPE_CUMULATIVE
    sample_stats_key = 'read_bytes'


class WriteRequestsPollster(AggregateDiskPollster):
    sample_name = 'disk.write.requests'
    sample_unit = 'request'
    sample_type = sample.TYPE_CUMULATIVE
    sample_stats_key = 'write_requests'


class PerDeviceWriteRequestsPollster(PerDeviceDiskPollster):
    sample_name = 'disk.device.write.requests'
    sample_unit = 'request'
    sample_type = sample.TYPE_CUMULATIVE
    sample_stats_key = 'write_requests'


class WriteBytesPollster(AggregateDiskPollster):
    sample_name = 'disk.write.bytes'
    sample_unit = 'B'
    sample_type = sample.TYPE_CUMULATIVE
    sample_stats_key = 'write_bytes'


class PerDeviceWriteBytesPollster(PerDeviceDiskPollster):
    sample_name = 'disk.device.write.bytes'
    sample_unit = 'B'
    sample_type = sample.TYPE_CUMULATIVE
    sample_stats_key = 'write_bytes'


class ReadBytesRatePollster(AggregateDiskPollster):
    inspector_method = "inspect_disk_rates"
    sample_name = 'disk.read.bytes.rate'
    sample_unit = 'B/s'
    sample_stats_key = 'read_bytes_rate'


class PerDeviceReadBytesRatePollster(PerDeviceDiskPollster):
    inspector_method = "inspect_disk_rates"
    sample_name = 'disk.device.read.bytes.rate'
    sample_unit = 'B/s'
    sample_stats_key = 'read_bytes_rate'


class ReadRequestsRatePollster(AggregateDiskPollster):
    inspector_method = "inspect_disk_rates"
    sample_name = 'disk.read.requests.rate'
    sample_unit = 'request/s'
    sample_stats_key = 'read_requests_rate'


class PerDeviceReadRequestsRatePollster(PerDeviceDiskPollster):
    inspector_method = "inspect_disk_rates"
    sample_name = 'disk.device.read.requests.rate'
    sample_unit = 'request/s'
    sample_stats_key = 'read_requests_rate'


class WriteBytesRatePollster(AggregateDiskPollster):
    inspector_method = "inspect_disk_rates"
    sample_name = 'disk.write.bytes.rate'
    sample_unit = 'B/s'
    sample_stats_key = 'write_bytes_rate'


class PerDeviceWriteBytesRatePollster(PerDeviceDiskPollster):
    inspector_method = "inspect_disk_rates"
    sample_name = 'disk.device.write.bytes.rate'
    sample_unit = 'B/s'
    sample_stats_key = 'write_bytes_rate'


class WriteRequestsRatePollster(AggregateDiskPollster):
    inspector_method = "inspect_disk_rates"
    sample_name = 'disk.write.requests.rate'
    sample_unit = 'request/s'
    sample_stats_key = 'write_requests_rate'


class PerDeviceWriteRequestsRatePollster(PerDeviceDiskPollster):
    inspector_method = "inspect_disk_rates"
    sample_name = 'disk.device.write.requests.rate'
    sample_unit = 'request/s'
    sample_stats_key = 'write_requests_rate'


class DiskLatencyPollster(AggregateDiskPollster):
    inspector_method = 'inspect_disk_latency'
    sample_name = 'disk.latency'
    sample_unit = 'ms'
    sample_stats_key = 'disk_latency'


class PerDeviceDiskLatencyPollster(PerDeviceDiskPollster):
    inspector_method = 'inspect_disk_latency'
    sample_name = 'disk.device.latency'
    sample_unit = 'ms'
    sample_stats_key = 'disk_latency'


class DiskIOPSPollster(AggregateDiskPollster):
    inspector_method = 'inspect_disk_iops'
    sample_name = 'disk.iops'
    sample_unit = 'count/s'
    sample_stats_key = 'iops_count'


class PerDeviceDiskIOPSPollster(PerDeviceDiskPollster):
    inspector_method = 'inspect_disk_iops'
    sample_name = 'disk.device.iops'
    sample_unit = 'count/s'
    sample_stats_key = 'iops_count'


class CapacityPollster(AggregateDiskPollster):
    inspector_method = 'inspect_disk_info'
    sample_name = 'disk.capacity'
    sample_unit = 'B'
    sample_stats_key = 'capacity'


class PerDeviceCapacityPollster(PerDeviceDiskPollster):
    inspector_method = 'inspect_disk_info'
    sample_name = 'disk.device.capacity'
    sample_unit = 'B'
    sample_stats_key = 'capacity'


class AllocationPollster(AggregateDiskPollster):
    inspector_method = 'inspect_disk_info'
    sample_name = 'disk.allocation'
    sample_unit = 'B'
    sample_stats_key = 'allocation'


class PerDeviceAllocationPollster(PerDeviceDiskPollster):
    inspector_method = 'inspect_disk_info'
    sample_name = 'disk.device.allocation'
    sample_unit = 'B'
    sample_stats_key = 'allocation'


class PhysicalPollster(AggregateDiskPollster):
    inspector_method = 'inspect_disk_info'
    sample_name = 'disk.usage'
    sample_unit = 'B'
    sample_stats_key = 'physical'


class PerDevicePhysicalPollster(PerDeviceDiskPollster):
    inspector_method = 'inspect_disk_info'
    sample_name = 'disk.device.usage'
    sample_unit = 'B'
    sample_stats_key = 'physical'
