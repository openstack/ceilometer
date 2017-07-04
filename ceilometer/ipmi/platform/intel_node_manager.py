# Copyright 2014 Intel Corporation.
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

"""Node manager engine to collect power and temperature of compute node.

Intel Node Manager Technology enables the datacenter IT to monitor and control
actual server power, thermal and compute utilization behavior through industry
defined standard IPMI. This file provides Node Manager engine to get simple
system power and temperature data based on ipmitool.
"""

import binascii
import collections
import tempfile
import threading
import time

from oslo_config import cfg
import six

from ceilometer.i18n import _
from ceilometer.ipmi.platform import exception as nmexcept
from ceilometer.ipmi.platform import ipmitool


OPTS = [
    cfg.IntOpt('node_manager_init_retry',
               default=3,
               help='Number of retries upon Intel Node '
                    'Manager initialization failure')
]


IPMICMD = {"sdr_dump": "sdr dump",
           "sdr_info": "sdr info",
           "sensor_dump": "sdr -v"}
IPMIRAWCMD = {"get_device_id": "raw 0x06 0x01",
              "get_nm_version": "raw 0x2e 0xca 0x57 0x01 0x00",
              "init_sensor_agent": "raw 0x0a 0x2c 0x01",
              "init_complete": "raw 0x0a 0x2c 0x00",
              "init_sensor_agent_status": "raw 0x0a 0x2c 0x00",
              "read_power_all": "raw 0x2e 0xc8 0x57 0x01 0x00 0x01 0x00 0x00",
              "read_inlet_temperature":
              "raw 0x2e 0xc8 0x57 0x01 0x00 0x02 0x00 0x00",
              "read_outlet_temperature":
              "raw 0x2e 0xc8 0x57 0x01 0x00 0x05 0x00 0x00",
              "read_airflow": "raw 0x2e 0xc8 0x57 0x01 0x00 0x04 0x00 0x00",
              "read_cups_utilization": "raw 0x2e 0x65 0x57 0x01 0x00 0x05",
              "read_cups_index": "raw 0x2e 0x65 0x57 0x01 0x00 0x01"}

MANUFACTURER_ID_INTEL = ['57', '01', '00']
INTEL_PREFIX = '5701000d01'

# The template dict are made according to the spec. It contains the expected
# length of each item. And it can be used to parse the output of IPMI command.

ONE_RETURN_TEMPLATE = {"ret": 1}

BMC_INFO_TEMPLATE = collections.OrderedDict()
BMC_INFO_TEMPLATE['Device_ID'] = 1
BMC_INFO_TEMPLATE['Device_Revision'] = 1
BMC_INFO_TEMPLATE['Firmware_Revision_1'] = 1
BMC_INFO_TEMPLATE['Firmware_Revision_2'] = 1
BMC_INFO_TEMPLATE['IPMI_Version'] = 1
BMC_INFO_TEMPLATE['Additional_Device_support'] = 1
BMC_INFO_TEMPLATE['Manufacturer_ID'] = 3
BMC_INFO_TEMPLATE['Product_ID'] = 2
BMC_INFO_TEMPLATE['Auxiliary_Firmware_Revision'] = 4

NM_STATISTICS_TEMPLATE = collections.OrderedDict()
NM_STATISTICS_TEMPLATE['Manufacturer_ID'] = 3
NM_STATISTICS_TEMPLATE['Current_value'] = 2
NM_STATISTICS_TEMPLATE['Minimum_value'] = 2
NM_STATISTICS_TEMPLATE['Maximum_value'] = 2
NM_STATISTICS_TEMPLATE['Average_value'] = 2
NM_STATISTICS_TEMPLATE['Time_stamp'] = 4
NM_STATISTICS_TEMPLATE['Report_period'] = 4
NM_STATISTICS_TEMPLATE["DomainID_PolicyState"] = 1

NM_GET_DEVICE_ID_TEMPLATE = collections.OrderedDict()
NM_GET_DEVICE_ID_TEMPLATE['Device_ID'] = 1
NM_GET_DEVICE_ID_TEMPLATE['Device_revision'] = 1
NM_GET_DEVICE_ID_TEMPLATE['Firmware_revision_1'] = 1
NM_GET_DEVICE_ID_TEMPLATE['Firmware_Revision_2'] = 1
NM_GET_DEVICE_ID_TEMPLATE['IPMI_Version'] = 1
NM_GET_DEVICE_ID_TEMPLATE['Additional_Device_support'] = 1
NM_GET_DEVICE_ID_TEMPLATE['Manufacturer_ID'] = 3
NM_GET_DEVICE_ID_TEMPLATE['Product_ID_min_version'] = 1
NM_GET_DEVICE_ID_TEMPLATE['Product_ID_major_version'] = 1
NM_GET_DEVICE_ID_TEMPLATE['Implemented_firmware'] = 1
NM_GET_DEVICE_ID_TEMPLATE['Firmware_build_number'] = 1
NM_GET_DEVICE_ID_TEMPLATE['Last_digit_firmware_build_number'] = 1
NM_GET_DEVICE_ID_TEMPLATE['Image_flags'] = 1

NM_GET_VERSION_TEMPLATE = collections.OrderedDict()
NM_GET_VERSION_TEMPLATE['Manufacturer_ID'] = 3
NM_GET_VERSION_TEMPLATE['NM_Version'] = 1
NM_GET_VERSION_TEMPLATE['IPMI_Version'] = 1
NM_GET_VERSION_TEMPLATE['Patch_Version'] = 1
NM_GET_VERSION_TEMPLATE['Firmware_Revision_Major'] = 1
NM_GET_VERSION_TEMPLATE['Firmware_Revision_Minor'] = 1

NM_CUPS_UTILIZATION_TEMPLATE = collections.OrderedDict()
NM_CUPS_UTILIZATION_TEMPLATE['Manufacturer_ID'] = 3
NM_CUPS_UTILIZATION_TEMPLATE['CPU_Utilization'] = 8
NM_CUPS_UTILIZATION_TEMPLATE['Mem_Utilization'] = 8
NM_CUPS_UTILIZATION_TEMPLATE['IO_Utilization'] = 8

NM_CUPS_INDEX_TEMPLATE = collections.OrderedDict()
NM_CUPS_INDEX_TEMPLATE['Manufacturer_ID'] = 3
NM_CUPS_INDEX_TEMPLATE['CUPS_Index'] = 2


def _hex(list=None):
    """Format the return value in list into hex."""

    list = list or []
    if list:
        list.reverse()
        return int(''.join(list), 16)

    return 0


class NodeManager(object):
    """The python implementation of Intel Node Manager engine using ipmitool

    The class implements the engine to read power and temperature of
    compute node. It uses ipmitool to execute the IPMI command and parse
    the output into dict.
    """
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Singleton to avoid duplicated initialization."""
        if cls._instance:
            # Shortcut with no lock
            return cls._instance
        with cls._instance_lock:
            if not cls._instance:
                cls._instance = super(NodeManager, cls).__new__(
                    cls, *args, **kwargs)
        return cls._instance

    def __init__(self, conf):
        self.conf = conf
        self.nm_version = 0
        self.channel_slave = ''
        self.nm_version = self.check_node_manager()

    @staticmethod
    def _parse_slave_and_channel(file_path):
        """Parse the dumped file to get slave address and channel number.

        :param file_path: file path of dumped SDR file.
        :return: slave address and channel number of target device or None if
                 not found.
        """
        prefix = INTEL_PREFIX
        # According to Intel Node Manager spec, section 4.5, for Intel NM
        # discovery OEM SDR records are type C0h. It contains manufacture ID
        # and OEM data in the record body.
        # 0-2 bytes are OEM ID, byte 3 is 0Dh and byte 4 is 01h. Byte 5, 6
        # is Intel NM device slave address and channel number/sensor owner LUN.
        with open(file_path, 'rb') as bin_fp:
            data_str = binascii.hexlify(bin_fp.read())

        if six.PY3:
            data_str = data_str.decode('ascii')
        oem_id_index = data_str.find(prefix)
        if oem_id_index != -1:
            ret = data_str[oem_id_index + len(prefix):
                           oem_id_index + len(prefix) + 4]
            # Byte 5 is slave address. [7:4] from byte 6 is channel
            # number, so just pick ret[2] here.
            return (ret[0:2], ret[2])

    @ipmitool.execute_ipmi_cmd(BMC_INFO_TEMPLATE)
    def get_device_id(self):
        """IPMI command GET_DEVICE_ID."""
        return IPMIRAWCMD["get_device_id"]

    @ipmitool.execute_ipmi_cmd(ONE_RETURN_TEMPLATE)
    def _init_sensor_agent(self):
        """Run initialization agent."""
        return IPMIRAWCMD["init_sensor_agent"]

    @ipmitool.execute_ipmi_cmd(ONE_RETURN_TEMPLATE)
    def _init_sensor_agent_process(self):
        """Check the status of initialization agent."""
        return IPMIRAWCMD["init_sensor_agent_status"]

    @ipmitool.execute_ipmi_cmd()
    def _dump_sdr_file(self, data_file=""):
        """Dump SDR into a file."""
        return IPMICMD["sdr_dump"] + " " + data_file

    @ipmitool.execute_ipmi_cmd(NM_GET_DEVICE_ID_TEMPLATE)
    def _node_manager_get_device_id(self):
        """GET_DEVICE_ID command in Intel Node Manager

        Different from IPMI command GET_DEVICE_ID, it contains more information
        of Intel Node Manager.
        """
        return self.channel_slave + ' ' + IPMIRAWCMD["get_device_id"]

    @ipmitool.execute_ipmi_cmd(NM_GET_VERSION_TEMPLATE)
    def _node_manager_get_version(self):
        """GET_NODE_MANAGER_VERSION command in Intel Node Manager

        Byte 4 of the response:
        01h - Intel NM 1.0
        02h - Intel NM 1.5
        03h - Intel NM 2.0
        04h - Intel NM 2.5
        05h - Intel NM 3.0
        """
        return self.channel_slave + ' ' + IPMIRAWCMD["get_nm_version"]

    @ipmitool.execute_ipmi_cmd(NM_STATISTICS_TEMPLATE)
    def _read_power_all(self):
        """Get the power consumption of the whole platform."""
        return self.channel_slave + ' ' + IPMIRAWCMD['read_power_all']

    @ipmitool.execute_ipmi_cmd(NM_STATISTICS_TEMPLATE)
    def _read_inlet_temperature(self):
        """Get the inlet temperature info of the whole platform."""
        return self.channel_slave + ' ' + IPMIRAWCMD['read_inlet_temperature']

    @ipmitool.execute_ipmi_cmd(NM_STATISTICS_TEMPLATE)
    def _read_outlet_temperature(self):
        """Get the outlet temperature info of the whole platform."""
        return self.channel_slave + ' ' + IPMIRAWCMD['read_outlet_temperature']

    @ipmitool.execute_ipmi_cmd(NM_STATISTICS_TEMPLATE)
    def _read_airflow(self):
        """Get the volumetric airflow of the whole platform."""
        return self.channel_slave + ' ' + IPMIRAWCMD['read_airflow']

    @ipmitool.execute_ipmi_cmd(NM_CUPS_UTILIZATION_TEMPLATE)
    def _read_cups_utilization(self):
        """Get the average CUPS utilization of the whole platform."""
        return self.channel_slave + ' ' + IPMIRAWCMD['read_cups_utilization']

    @ipmitool.execute_ipmi_cmd(NM_CUPS_INDEX_TEMPLATE)
    def _read_cups_index(self):
        """Get the CUPS Index of the whole platform."""
        return self.channel_slave + ' ' + IPMIRAWCMD['read_cups_index']

    def read_power_all(self):
        return self._read_power_all() if self.nm_version > 0 else {}

    def read_inlet_temperature(self):
        return self._read_inlet_temperature() if self.nm_version > 0 else {}

    def read_outlet_temperature(self):
        return self._read_outlet_temperature() if self.nm_version >= 5 else {}

    def read_airflow(self):
        # only available after NM 3.0
        return self._read_airflow() if self.nm_version >= 5 else {}

    def read_cups_utilization(self):
        # only available after NM 3.0
        return self._read_cups_utilization() if self.nm_version >= 5 else {}

    def read_cups_index(self):
        # only available after NM 3.0
        return self._read_cups_index() if self.nm_version >= 5 else {}

    def init_node_manager(self):
        if self._init_sensor_agent_process()['ret'] == ['01']:
            return
        # Run sensor initialization agent
        for i in range(self.conf.ipmi.node_manager_init_retry):
            self._init_sensor_agent()
            time.sleep(1)
            if self._init_sensor_agent_process()['ret'] == ['01']:
                return

        raise nmexcept.NodeManagerException(_('Node Manager init failed'))

    def discover_slave_channel(self):
        """Discover target slave address and channel number."""
        file_path = tempfile.mkstemp()[1]
        self._dump_sdr_file(data_file=file_path)
        ret = self._parse_slave_and_channel(file_path)
        slave_address = ''.join(['0x', ret[0]])
        channel = ''.join(['0x', ret[1]])
        # String of channel and slave_address
        self.channel_slave = '-b ' + channel + ' -t ' + slave_address

    def node_manager_version(self):
        """Intel Node Manager capability checking

        This function is used to detect if compute node support Intel Node
        Manager(return version number) or not(return -1) and parse out the
        slave address and channel number of node manager.
        """
        self.manufacturer_id = self.get_device_id()['Manufacturer_ID']
        if MANUFACTURER_ID_INTEL != self.manufacturer_id:
            # If the manufacturer is not Intel, just set False and return.
            return 0

        self.discover_slave_channel()
        support = self._node_manager_get_device_id()['Implemented_firmware']
        # According to Intel Node Manager spec, return value of GET_DEVICE_ID,
        # bits 3 to 0 shows if Intel NM implemented or not.
        if int(support[0], 16) & 0xf == 0:
            return 0

        return _hex(self._node_manager_get_version()['NM_Version'])

    def check_node_manager(self):
        """Intel Node Manager init and check

        This function is used to initialize Intel Node Manager and check the
        capability without throwing exception. It's safe to call it on
        non-NodeManager platform.
        """
        try:
            self.init_node_manager()
            nm_version = self.node_manager_version()
        except (nmexcept.NodeManagerException, nmexcept.IPMIException):
            return 0
        return nm_version
