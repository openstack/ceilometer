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
"""Inspector for collecting data over SNMP"""

from pysnmp.entity.rfc3413.oneliner import cmdgen
from six.moves.urllib import parse as urlparse

from ceilometer.hardware.inspector import base


class SNMPException(Exception):
    pass


def parse_snmp_return(ret):
    """Check the return value of snmp operations

    :param ret: a tuple of (errorIndication, errorStatus, errorIndex, data)
                returned by pysnmp
    :return: a tuple of (err, data)
             err: True if error found, or False if no error found
             data: a string of error description if error found, or the
                   actual return data of the snmp operation
    """
    err = True
    (errIndication, errStatus, errIdx, varBinds) = ret
    if errIndication:
        data = errIndication
    elif errStatus:
        data = "%s at %s" % (errStatus.prettyPrint(),
                             errIdx and varBinds[int(errIdx) - 1] or "?")
    else:
        err = False
        data = varBinds
    return (err, data)


class SNMPInspector(base.Inspector):
    # CPU OIDs
    _cpu_1_min_load_oid = "1.3.6.1.4.1.2021.10.1.3.1"
    _cpu_5_min_load_oid = "1.3.6.1.4.1.2021.10.1.3.2"
    _cpu_15_min_load_oid = "1.3.6.1.4.1.2021.10.1.3.3"
    # Memory OIDs
    _memory_total_oid = "1.3.6.1.4.1.2021.4.5.0"
    _memory_used_oid = "1.3.6.1.4.1.2021.4.6.0"
    # Disk OIDs
    _disk_index_oid = "1.3.6.1.4.1.2021.9.1.1"
    _disk_path_oid = "1.3.6.1.4.1.2021.9.1.2"
    _disk_device_oid = "1.3.6.1.4.1.2021.9.1.3"
    _disk_size_oid = "1.3.6.1.4.1.2021.9.1.6"
    _disk_used_oid = "1.3.6.1.4.1.2021.9.1.8"
    # Network Interface OIDs
    _interface_index_oid = "1.3.6.1.2.1.2.2.1.1"
    _interface_name_oid = "1.3.6.1.2.1.2.2.1.2"
    _interface_speed_oid = "1.3.6.1.2.1.2.2.1.5"
    _interface_mac_oid = "1.3.6.1.2.1.2.2.1.6"
    _interface_ip_oid = "1.3.6.1.2.1.4.20.1.2"
    _interface_received_oid = "1.3.6.1.2.1.2.2.1.10"
    _interface_transmitted_oid = "1.3.6.1.2.1.2.2.1.16"
    _interface_error_oid = "1.3.6.1.2.1.2.2.1.20"
    # Default port and security name
    _port = 161
    _security_name = 'public'

    def __init__(self):
        super(SNMPInspector, self).__init__()
        self._cmdGen = cmdgen.CommandGenerator()

    def _get_or_walk_oid(self, oid, host, get=True):
        if get:
            func = self._cmdGen.getCmd
            ret_func = lambda x: x[0][1]
        else:
            func = self._cmdGen.nextCmd
            ret_func = lambda x: x
        ret = func(cmdgen.CommunityData(self._get_security_name(host)),
                   cmdgen.UdpTransportTarget((host.hostname,
                                              host.port or self._port)),
                   oid)
        (error, data) = parse_snmp_return(ret)
        if error:
            raise SNMPException("An error occurred, oid %(oid)s, "
                                "host %(host)s, %(err)s" %
                                dict(oid=oid, host=host.hostname, err=data))
        else:
            return ret_func(data)

    def _get_value_from_oid(self, oid, host):
        return self._get_or_walk_oid(oid, host, True)

    def _walk_oid(self, oid, host):
        return self._get_or_walk_oid(oid, host, False)

    def inspect_cpu(self, host):
        # get 1 minute load
        cpu_1_min_load = \
            str(self._get_value_from_oid(self._cpu_1_min_load_oid, host))
        # get 5 minute load
        cpu_5_min_load = \
            str(self._get_value_from_oid(self._cpu_5_min_load_oid, host))
        # get 15 minute load
        cpu_15_min_load = \
            str(self._get_value_from_oid(self._cpu_15_min_load_oid, host))

        yield base.CPUStats(cpu_1_min=float(cpu_1_min_load),
                            cpu_5_min=float(cpu_5_min_load),
                            cpu_15_min=float(cpu_15_min_load))

    def inspect_memory(self, host):
        # get total memory
        total = self._get_value_from_oid(self._memory_total_oid, host)
        # get used memory
        used = self._get_value_from_oid(self._memory_used_oid, host)

        yield base.MemoryStats(total=int(total), used=int(used))

    def inspect_disk(self, host):
        disks = self._walk_oid(self._disk_index_oid, host)

        for disk in disks:
            for object_name, value in disk:
                path_oid = "%s.%s" % (self._disk_path_oid, str(value))
                path = self._get_value_from_oid(path_oid, host)
                device_oid = "%s.%s" % (self._disk_device_oid, str(value))
                device = self._get_value_from_oid(device_oid, host)
                size_oid = "%s.%s" % (self._disk_size_oid, str(value))
                size = self._get_value_from_oid(size_oid, host)
                used_oid = "%s.%s" % (self._disk_used_oid, str(value))
                used = self._get_value_from_oid(used_oid, host)

                disk = base.Disk(device=str(device),
                                 path=str(path))
                stats = base.DiskStats(size=int(size),
                                       used=int(used))

                yield (disk, stats)

    def inspect_network(self, host):
        net_interfaces = self._walk_oid(self._interface_index_oid, host)

        for interface in net_interfaces:
            for object_name, value in interface:
                ip = self._get_ip_for_interface(host, value)
                name_oid = "%s.%s" % (self._interface_name_oid,
                                      str(value))
                name = self._get_value_from_oid(name_oid, host)
                mac_oid = "%s.%s" % (self._interface_mac_oid,
                                     str(value))
                mac = self._get_value_from_oid(mac_oid, host)
                speed_oid = "%s.%s" % (self._interface_speed_oid,
                                       str(value))
                # bits/s to byte/s
                speed = self._get_value_from_oid(speed_oid, host) / 8
                rx_oid = "%s.%s" % (self._interface_received_oid,
                                    str(value))
                rx_bytes = self._get_value_from_oid(rx_oid, host)
                tx_oid = "%s.%s" % (self._interface_transmitted_oid,
                                    str(value))
                tx_bytes = self._get_value_from_oid(tx_oid, host)
                error_oid = "%s.%s" % (self._interface_error_oid,
                                       str(value))
                error = self._get_value_from_oid(error_oid, host)

                adapted_mac = mac.prettyPrint().replace('0x', '')
                interface = base.Interface(name=str(name),
                                           mac=adapted_mac,
                                           ip=str(ip),
                                           speed=int(speed))
                stats = base.InterfaceStats(rx_bytes=int(rx_bytes),
                                            tx_bytes=int(tx_bytes),
                                            error=int(error))
                yield (interface, stats)

    def _get_security_name(self, host):
        options = urlparse.parse_qs(host.query)
        return options.get('security_name', [self._security_name])[-1]

    def _get_ip_for_interface(self, host, interface_id):
        ip_addresses = self._walk_oid(self._interface_ip_oid, host)
        for ip in ip_addresses:
            for name, value in ip:
                if value == interface_id:
                    return str(name).replace(self._interface_ip_oid + ".", "")
