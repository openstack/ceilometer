#
# Copyright 2012 eNovance <licensing@enovance.com>
# Copyright 2012 Red Hat, Inc
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


class InstanceStatsPollster(pollsters.GenericComputePollster):
    inspector_method = 'inspect_instance'


class CPUPollster(InstanceStatsPollster):
    sample_name = 'cpu'
    sample_unit = 'ns'
    sample_stats_key = 'cpu_time'
    sample_type = sample.TYPE_CUMULATIVE

    @staticmethod
    def get_additional_metadata(instance, c_data):
        return {'cpu_number': c_data.cpu_number}


class CPUUtilPollster(InstanceStatsPollster):
    sample_name = 'cpu_util'
    sample_unit = '%'
    sample_stats_key = 'cpu_util'


class MemoryUsagePollster(InstanceStatsPollster):
    sample_name = 'memory.usage'
    sample_unit = 'MB'
    sample_stats_key = 'memory_usage'


class MemoryResidentPollster(InstanceStatsPollster):
    sample_name = 'memory.resident'
    sample_unit = 'MB'
    sample_stats_key = 'memory_resident'


class MemorySwapInPollster(InstanceStatsPollster):
    sample_name = 'memory.swap.in'
    sample_unit = 'MB'
    sample_stats_key = 'memory_swap_in'
    sample_type = sample.TYPE_CUMULATIVE


class MemorySwapOutPollster(InstanceStatsPollster):
    sample_name = 'memory.swap.out'
    sample_unit = 'MB'
    sample_stats_key = 'memory_swap_out'
    sample_type = sample.TYPE_CUMULATIVE


class PerfCPUCyclesPollster(InstanceStatsPollster):
    sample_name = 'perf.cpu.cycles'
    sample_stats_key = 'cpu_cycles'


class PerfInstructionsPollster(InstanceStatsPollster):
    sample_name = 'perf.instructions'
    sample_stats_key = 'instructions'


class PerfCacheReferencesPollster(InstanceStatsPollster):
    sample_name = 'perf.cache.references'
    sample_stats_key = 'cache_references'


class PerfCacheMissesPollster(InstanceStatsPollster):
    sample_name = 'perf.cache.misses'
    sample_stats_key = 'cache_misses'


class MemoryBandwidthTotalPollster(InstanceStatsPollster):
    sample_name = 'memory.bandwidth.total'
    sample_unit = 'B/s'
    sample_stats_key = 'memory_bandwidth_total'


class MemoryBandwidthLocalPollster(InstanceStatsPollster):
    sample_name = 'memory.bandwidth.local'
    sample_unit = 'B/s'
    sample_stats_key = 'memory_bandwidth_local'


class CPUL3CachePollster(InstanceStatsPollster):
    sample_name = 'cpu_l3_cache'
    sample_unit = 'B'
    sample_stats_key = "cpu_l3_cache_usage"
