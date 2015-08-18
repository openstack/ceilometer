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
from ceilometer.i18n import _


OPTS = [
    cfg.StrOpt('hypervisor_inspector',
               default='libvirt',
               help='Inspector to use for inspecting the hypervisor layer. '
                    'Known inspectors are libvirt, hyperv, vmware, xenapi '
                    'and powervm.'),
]

cfg.CONF.register_opts(OPTS)


LOG = log.getLogger(__name__)

# Named tuple representing instances.
#
# name: the name of the instance
# uuid: the UUID associated with the instance
#
Instance = collections.namedtuple('Instance', ['name', 'UUID'])


# Named tuple representing CPU statistics.
#
# number: number of CPUs
# time: cumulative CPU time
#
CPUStats = collections.namedtuple('CPUStats', ['number', 'time'])

# Named tuple representing CPU Utilization statistics.
#
# util: CPU utilization in percentage
#
CPUUtilStats = collections.namedtuple('CPUUtilStats', ['util'])

# Named tuple representing Memory usage statistics.
#
# usage: Amount of memory used
#
MemoryUsageStats = collections.namedtuple('MemoryUsageStats', ['usage'])


# Named tuple representing Resident Memory usage statistics.
#
# resident: Amount of resident memory
#
MemoryResidentStats = collections.namedtuple('MemoryResidentStats',
                                             ['resident'])


# Named tuple representing vNICs.
#
# name: the name of the vNIC
# mac: the MAC address
# fref: the filter ref
# parameters: miscellaneous parameters
#
Interface = collections.namedtuple('Interface', ['name', 'mac',
                                                 'fref', 'parameters'])


# Named tuple representing vNIC statistics.
#
# rx_bytes: number of received bytes
# rx_packets: number of received packets
# tx_bytes: number of transmitted bytes
# tx_packets: number of transmitted packets
#
InterfaceStats = collections.namedtuple('InterfaceStats',
                                        ['rx_bytes', 'rx_packets',
                                         'tx_bytes', 'tx_packets'])


# Named tuple representing vNIC rate statistics.
#
# rx_bytes_rate: rate of received bytes
# tx_bytes_rate: rate of transmitted bytes
#
InterfaceRateStats = collections.namedtuple('InterfaceRateStats',
                                            ['rx_bytes_rate', 'tx_bytes_rate'])


# Named tuple representing disks.
#
# device: the device name for the disk
#
Disk = collections.namedtuple('Disk', ['device'])


# Named tuple representing disk statistics.
#
# read_bytes: number of bytes read
# read_requests: number of read operations
# write_bytes: number of bytes written
# write_requests: number of write operations
# errors: number of errors
#
DiskStats = collections.namedtuple('DiskStats',
                                   ['read_bytes', 'read_requests',
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
                                       ['read_bytes_rate',
                                        'read_requests_rate',
                                        'write_bytes_rate',
                                        'write_requests_rate'])

# Named tuple representing disk latency statistics.
#
# disk_latency: average disk latency
#
DiskLatencyStats = collections.namedtuple('DiskLatencyStats',
                                          ['disk_latency'])

# Named tuple representing disk iops statistics.
#
# iops: number of iops per second
#
DiskIOPSStats = collections.namedtuple('DiskIOPSStats',
                                       ['iops_count'])


# Named tuple representing disk Information.
#
# capacity: capacity of the disk
# allocation: allocation of the disk
# physical: usage of the disk

DiskInfo = collections.namedtuple('DiskInfo',
                                  ['capacity',
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


class NoSanityException(InspectorException):
    pass


# Main virt inspector abstraction layering over the hypervisor API.
#
class Inspector(object):

    def check_sanity(self):
        """Check the sanity of hypervisor inspector.

        Each subclass could overwrite it to throw any exception
        when detecting mis-configured inspector
        """
        pass

    def inspect_cpus(self, instance):
        """Inspect the CPU statistics for an instance.

        :param instance: the target instance
        :return: the number of CPUs and cumulative CPU time
        """
        raise ceilometer.NotImplementedError

    def inspect_cpu_util(self, instance, duration=None):
        """Inspect the CPU Utilization (%) for an instance.

        :param instance: the target instance
        :param duration: the last 'n' seconds, over which the value should be
               inspected
        :return: the percentage of CPU utilization
        """
        raise ceilometer.NotImplementedError

    def inspect_vnics(self, instance):
        """Inspect the vNIC statistics for an instance.

        :param instance: the target instance
        :return: for each vNIC, the number of bytes & packets
                 received and transmitted
        """
        raise ceilometer.NotImplementedError

    def inspect_vnic_rates(self, instance, duration=None):
        """Inspect the vNIC rate statistics for an instance.

        :param instance: the target instance
        :param duration: the last 'n' seconds, over which the value should be
               inspected
        :return: for each vNIC, the rate of bytes & packets
                 received and transmitted
        """
        raise ceilometer.NotImplementedError

    def inspect_disks(self, instance):
        """Inspect the disk statistics for an instance.

        :param instance: the target instance
        :return: for each disk, the number of bytes & operations
                 read and written, and the error count
        """
        raise ceilometer.NotImplementedError

    def inspect_memory_usage(self, instance, duration=None):
        """Inspect the memory usage statistics for an instance.

        :param instance: the target instance
        :param duration: the last 'n' seconds, over which the value should be
               inspected
        :return: the amount of memory used
        """
        raise ceilometer.NotImplementedError

    def inspect_memory_resident(self, instance, duration=None):
        """Inspect the resident memory statistics for an instance.

        :param instance: the target instance
        :param duration: the last 'n' seconds, over which the value should be
               inspected
        :return: the amount of resident memory
        """
        raise ceilometer.NotImplementedError

    def inspect_disk_rates(self, instance, duration=None):
        """Inspect the disk statistics as rates for an instance.

        :param instance: the target instance
        :param duration: the last 'n' seconds, over which the value should be
               inspected
        :return: for each disk, the number of bytes & operations
                 read and written per second, with the error count
        """
        raise ceilometer.NotImplementedError

    def inspect_disk_latency(self, instance):
        """Inspect the disk statistics as rates for an instance.

        :param instance: the target instance
        :return: for each disk, the average disk latency
        """
        raise ceilometer.NotImplementedError

    def inspect_disk_iops(self, instance):
        """Inspect the disk statistics as rates for an instance.

        :param instance: the target instance
        :return: for each disk, the number of iops per second
        """
        raise ceilometer.NotImplementedError

    def inspect_disk_info(self, instance):
        """Inspect the disk information for an instance.

        :param instance: the target instance
        :return: for each disk , capacity , alloaction and usage
        """
        raise ceilometer.NotImplementedError


def get_hypervisor_inspector():
    try:
        namespace = 'ceilometer.compute.virt'
        mgr = driver.DriverManager(namespace,
                                   cfg.CONF.hypervisor_inspector,
                                   invoke_on_load=True)
        return mgr.driver
    except ImportError as e:
        LOG.error(_("Unable to load the hypervisor inspector: %s") % e)
        return Inspector()
