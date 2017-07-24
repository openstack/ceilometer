#
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
"""Inspector abstraction for read-only access to hypervisors."""

import collections

from oslo_config import cfg
from oslo_log import log
from stevedore import driver

import ceilometer


OPTS = [
    cfg.StrOpt('hypervisor_inspector',
               default='libvirt',
               help='Inspector to use for inspecting the hypervisor layer. '
                    'Known inspectors are libvirt, hyperv, vsphere '
                    'and xenapi.'),
]


LOG = log.getLogger(__name__)


# Named tuple representing instance statistics

class InstanceStats(object):
    fields = [
        'cpu_number',              # number: number of CPUs
        'cpu_time',                # time: cumulative CPU time
        'cpu_util',                # util: CPU utilization in percentage
        'cpu_l3_cache_usage',      # cachesize: Amount of CPU L3 cache used
        'memory_usage',            # usage: Amount of memory used
        'memory_resident',         #
        'memory_swap_in',          # memory swap in
        'memory_swap_out',         # memory swap out
        'memory_bandwidth_total',  # total: total system bandwidth from one
                                   #   level of cache
        'memory_bandwidth_local',  # local: bandwidth of memory traffic for a
                                   #   memory controller
        'cpu_cycles',              # cpu_cycles: the number of cpu cycles one
                                   #   instruction needs
        'instructions',            # instructions: the count of instructions
        'cache_references',        # cache_references: the count of cache hits
        'cache_misses',            # cache_misses: the count of caches misses
    ]

    def __init__(self, **kwargs):
        for k in self.fields:
            setattr(self, k, kwargs.pop(k, None))
        if kwargs:
            raise AttributeError(
                "'InstanceStats' object has no attributes '%s'" % kwargs)


# Named tuple representing vNIC statistics.
#
# name: the name of the vNIC
# mac: the MAC address
# fref: the filter ref
# parameters: miscellaneous parameters
# rx_bytes: number of received bytes
# rx_packets: number of received packets
# tx_bytes: number of transmitted bytes
# tx_packets: number of transmitted packets
#
InterfaceStats = collections.namedtuple('InterfaceStats',
                                        ['name', 'mac', 'fref', 'parameters',
                                         'rx_bytes', 'tx_bytes',
                                         'rx_packets', 'tx_packets',
                                         'rx_drop', 'tx_drop',
                                         'rx_errors', 'tx_errors'])


# Named tuple representing vNIC rate statistics.
#
# name: the name of the vNIC
# mac: the MAC address
# fref: the filter ref
# parameters: miscellaneous parameters
# rx_bytes_rate: rate of received bytes
# tx_bytes_rate: rate of transmitted bytes
#
InterfaceRateStats = collections.namedtuple('InterfaceRateStats',
                                            ['name', 'mac',
                                             'fref', 'parameters',
                                             'rx_bytes_rate', 'tx_bytes_rate'])


# Named tuple representing disk statistics.
#
# read_bytes: number of bytes read
# read_requests: number of read operations
# write_bytes: number of bytes written
# write_requests: number of write operations
# errors: number of errors
#
DiskStats = collections.namedtuple('DiskStats',
                                   ['device',
                                    'read_bytes', 'read_requests',
                                    'write_bytes', 'write_requests',
                                    'errors'])

# Named tuple representing disk rate statistics.
#
# read_bytes_rate: number of bytes read per second
# read_requests_rate: number of read operations per second
# write_bytes_rate: number of bytes written per second
# write_requests_rate: number of write operations per second
#
DiskRateStats = collections.namedtuple('DiskRateStats',
                                       ['device',
                                        'read_bytes_rate',
                                        'read_requests_rate',
                                        'write_bytes_rate',
                                        'write_requests_rate'])

# Named tuple representing disk latency statistics.
#
# disk_latency: average disk latency
#
DiskLatencyStats = collections.namedtuple('DiskLatencyStats',
                                          ['device', 'disk_latency'])

# Named tuple representing disk iops statistics.
#
# iops: number of iops per second
#
DiskIOPSStats = collections.namedtuple('DiskIOPSStats',
                                       ['device', 'iops_count'])


# Named tuple representing disk Information.
#
# capacity: capacity of the disk
# allocation: allocation of the disk
# physical: usage of the disk

DiskInfo = collections.namedtuple('DiskInfo',
                                  ['device',
                                   'capacity',
                                   'allocation',
                                   'physical'])


# Exception types
#
class InspectorException(Exception):
    def __init__(self, message=None):
        super(InspectorException, self).__init__(message)


class InstanceNotFoundException(InspectorException):
    pass


class InstanceShutOffException(InspectorException):
    pass


class NoDataException(InspectorException):
    pass


# Main virt inspector abstraction layering over the hypervisor API.
#
class Inspector(object):

    def __init__(self, conf):
        self.conf = conf

    def inspect_instance(self, instance, duration):
        """Inspect the CPU statistics for an instance.

        :param instance: the target instance
        :param duration: the last 'n' seconds, over which the value should be
               inspected
        :return: the instance stats
        """
        raise ceilometer.NotImplementedError

    def inspect_vnics(self, instance, duration):
        """Inspect the vNIC statistics for an instance.

        :param instance: the target instance
        :param duration: the last 'n' seconds, over which the value should be
               inspected
        :return: for each vNIC, the number of bytes & packets
                 received and transmitted
        """
        raise ceilometer.NotImplementedError

    def inspect_vnic_rates(self, instance, duration):
        """Inspect the vNIC rate statistics for an instance.

        :param instance: the target instance
        :param duration: the last 'n' seconds, over which the value should be
               inspected
        :return: for each vNIC, the rate of bytes & packets
                 received and transmitted
        """
        raise ceilometer.NotImplementedError

    def inspect_disks(self, instance, duration):
        """Inspect the disk statistics for an instance.

        :param instance: the target instance
        :param duration: the last 'n' seconds, over which the value should be
               inspected
        :return: for each disk, the number of bytes & operations
                 read and written, and the error count
        """
        raise ceilometer.NotImplementedError

    def inspect_disk_rates(self, instance, duration):
        """Inspect the disk statistics as rates for an instance.

        :param instance: the target instance
        :param duration: the last 'n' seconds, over which the value should be
               inspected
        :return: for each disk, the number of bytes & operations
                 read and written per second, with the error count
        """
        raise ceilometer.NotImplementedError

    def inspect_disk_latency(self, instance, duration):
        """Inspect the disk statistics as rates for an instance.

        :param instance: the target instance
        :param duration: the last 'n' seconds, over which the value should be
               inspected
        :return: for each disk, the average disk latency
        """
        raise ceilometer.NotImplementedError

    def inspect_disk_iops(self, instance, duration):
        """Inspect the disk statistics as rates for an instance.

        :param instance: the target instance
        :param duration: the last 'n' seconds, over which the value should be
               inspected
        :return: for each disk, the number of iops per second
        """
        raise ceilometer.NotImplementedError

    def inspect_disk_info(self, instance, duration):
        """Inspect the disk information for an instance.

        :param instance: the target instance
        :param duration: the last 'n' seconds, over which the value should be
               inspected
        :return: for each disk , capacity , allocation and usage
        """
        raise ceilometer.NotImplementedError


def get_hypervisor_inspector(conf):
    try:
        namespace = 'ceilometer.compute.virt'
        mgr = driver.DriverManager(namespace,
                                   conf.hypervisor_inspector,
                                   invoke_on_load=True,
                                   invoke_args=(conf, ))
        return mgr.driver
    except ImportError as e:
        LOG.error("Unable to load the hypervisor inspector: %s" % e)
        return Inspector(conf)
