#
# Copyright 2014 ZHAW SoE
#
# Authors: Lucas Graf <graflu0@students.zhaw.ch>
#          Toni Zehnder <zehndton@students.zhaw.ch>
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
"""Inspector abstraction for read-only access to hardware components"""

import abc
import collections

import six

# Named tuple representing CPU statistics.
#
# cpu1MinLoad: 1 minute load
# cpu5MinLoad: 5 minute load
# cpu15MinLoad: 15 minute load
#
CPUStats = collections.namedtuple(
    'CPUStats',
    ['cpu_1_min', 'cpu_5_min', 'cpu_15_min'])

# Named tuple representing RAM statistics.
#
# total: Total Memory (bytes)
# used: Used Memory (bytes)
#
MemoryStats = collections.namedtuple('MemoryStats', ['total', 'used'])

# Named tuple representing disks.
#
# device: the device name for the disk
# path: the path from the disk
#
Disk = collections.namedtuple('Disk', ['device', 'path'])

# Named tuple representing disk statistics.
#
# size: storage size (bytes)
# used: storage used (bytes)
#
DiskStats = collections.namedtuple('DiskStats', ['size', 'used'])


# Named tuple representing an interface.
#
# name: the name of the interface
# mac: the MAC of the interface
# ip: the IP of the interface
# speed: the speed of the interface (bytes/s)
#
Interface = collections.namedtuple('Interface', ['name', 'mac', 'ip', 'speed'])


# Named tuple representing network interface statistics.
#
# rx_bytes: total number of octets received (bytes)
# tx_bytes: total number of octets transmitted (bytes)
# error: number of outbound packets not transmitted because of errors
#
InterfaceStats = collections.namedtuple('InterfaceStats',
                                        ['rx_bytes', 'tx_bytes', 'error'])


@six.add_metaclass(abc.ABCMeta)
class Inspector(object):
    @abc.abstractmethod
    def inspect_cpu(self, host):
        """Inspect the CPU statistics for a host.

        :param host: the target host
        :return: iterator of CPUStats
        """

    @abc.abstractmethod
    def inspect_disk(self, host):
        """Inspect the disk statistics for a host.

        :param : the target host
        :return: iterator of tuple (Disk, DiskStats)
        """

    @abc.abstractmethod
    def inspect_memory(self, host):
        """Inspect the ram statistics for a host.

        :param : the target host
        :return: iterator of MemoryStats
        """

    @abc.abstractmethod
    def inspect_network(self, host):
        """Inspect the network interfaces for a host.

        :param : the target host
        :return: iterator of tuple (Interface, InterfaceStats)
        """
