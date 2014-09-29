# Copyright 2014 Intel Corporation.
# All Rights Reserved.
#
# Author: Zhai Edwin <edwin.zhai@intel.com>
# Author: Gao Fengqian <fengqian.gao@intel.com>
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
actual server power, thermal and compute utlization behavior through industry
defined standard IPMI. This file provides Node Manager engine to get simple
system power and temperature data based on ipmitool.
"""

import binascii
import tempfile
import time

from ceilometer.ipmi.platform import exception as nmexcept
from ceilometer.ipmi.platform import ipmitool
from ceilometer.openstack.common.gettextutils import _
from oslo.config import cfg


def get_ordereddict():
    """A fix for py26 not having ordereddict."""
    try:
        import collections
        return collections.OrderedDict
    except AttributeError:
        import ordereddict
        return ordereddict.OrderedDict

OrderedDict = get_ordereddict()

node_manager_init_retry = cfg.IntOpt('node_manager_init_retry',
                                     default=3,
                                     help='Number of retries upon Intel Node '
                                          'Manager initialization failure')


CONF = cfg.CONF
CONF.register_opt(node_manager_init_retry, group='ipmi')

IPMICMD = {"sdr_dump": "sdr dump",
           "sdr_info": "sdr info",
           "sensor_dump": "sdr -v"}
IPMIRAWCMD = {"get_device_id": "raw 0x06 0x01",
              "init_sensor_agent": "raw 0x0a 0x2c 0x01",
              "init_complete": "raw 0x0a 0x2c 0x00",
              "init_sensor_agent_status": "raw 0x0a 0x2c 0x00",
              "read_power_all": "raw 0x2e 0xc8 0x57 0x01 0x00 0x01 0x00 0x00",
              "read_temperature_all":
              "raw 0x2e 0xc8 0x57 0x01 0x00 0x02 0x00 0x00"}

MANUFACTURER_ID_INTEL = ['57', '01', '00']
INTEL_PREFIX = '5701000d01'

# The template dict are made according to the spec. It contains the expected
# length of each item. And it can be used to parse the output of IPMI command.

ONE_RETURN_TEMPLATE = {"ret": 1}

BMC_INFO_TEMPLATE = OrderedDict()
BMC_INFO_TEMPLATE['Device_ID'] = 1
BMC_INFO_TEMPLATE['Device_Revision'] = 1
BMC_INFO_TEMPLATE['Firmware_Revision_1'] = 1
BMC_INFO_TEMPLATE['Firmware_Revision_2'] = 1
BMC_INFO_TEMPLATE['IPMI_Version'] = 1
BMC_INFO_TEMPLATE['Additional_Device_support'] = 1
BMC_INFO_TEMPLATE['Manufacturer_ID'] = 3
BMC_INFO_TEMPLATE['Product_ID'] = 2
BMC_INFO_TEMPLATE['Auxiliary_Firmware_Revision'] = 4

NM_STATISTICS_TEMPLATE = OrderedDict()
NM_STATISTICS_TEMPLATE['Manufacturer_ID'] = 3
NM_STATISTICS_TEMPLATE['Current_value'] = 2
NM_STATISTICS_TEMPLATE['Minimum_value'] = 2
NM_STATISTICS_TEMPLATE['Maximum_value'] = 2
NM_STATISTICS_TEMPLATE['Average_value'] = 2
NM_STATISTICS_TEMPLATE['Time_stamp'] = 4
NM_STATISTICS_TEMPLATE['Report_period'] = 4
NM_STATISTICS_TEMPLATE["DomainID_PolicyState"] = 1

NM_GET_DEVICE_ID_TEMPLATE = OrderedDict()
NM_GET_DEVICE_ID_TEMPLATE['Device_ID'] = 1
NM_GET_DEVICE_ID_TEMPLATE['Device_revision'] = 1
NM_GET_DEVICE_ID_TEMPLATE['Firmware_revision_1'] = 1
NM_GET_DEVICE_ID_TEMPLATE['Firmware_Revision_2'] = 1
NM_GET_DEVICE_ID_TEMPLATE['IPMI_Version'] = 1
NM_GET_DEVICE_ID_TEMPLATE['Additinal_Device_support'] = 1
NM_GET_DEVICE_ID_TEMPLATE['Manufacturer_ID'] = 3
NM_GET_DEVICE_ID_TEMPLATE['Product_ID_min_version'] = 1
NM_GET_DEVICE_ID_TEMPLATE['Product_ID_major_version'] = 1
NM_GET_DEVICE_ID_TEMPLATE['Implemented_firmware'] = 1
NM_GET_DEVICE_ID_TEMPLATE['Firmware_build_number'] = 1
NM_GET_DEVICE_ID_TEMPLATE['Last_digit_firmware_build_number'] = 1
NM_GET_DEVICE_ID_TEMPLATE['Image_flags'] = 1


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
    _inited = False
    _instance = None

    def __new__(cls, *args, **kwargs):
        """Singleton to avoid duplicated initialization."""
        if not cls._instance:
            cls._instance = super(NodeManager, cls).__new__(cls, *args,
                                                            **kwargs)
        return cls._instance

    def __init__(self):
        if not (self._instance and self._inited):
            self.nm_support = False
            self.channel_slave = ''
            self._inited = True

            self.nm_support = self.check_node_manager()

    @staticmethod
    def _parse_slave_and_channel(file_path):
        """Parse the dumped file to get slave address and channel number.

        :param file_path: file path of dumped SDR file.
        :return: slave address and channel number of target device.
        """
        ret = None
        prefix = INTEL_PREFIX
        # According to Intel Node Manager spec, section 4.5, for Intel NM
        # discovery OEM SDR records are type C0h. It contains manufacture ID
        # and OEM data in the record body.
        # 0-2 bytes are OEM ID, byte 3 is 0Dh and byte 4 is 01h. Byte 5, 6
        # is Intel NM device slave address and channel number/sensor owner LUN.
        with open(file_path, 'rb') as bin_fp:
            for line in bin_fp.readlines():
                if line:
                    data_str = binascii.hexlify(line)
                    if prefix in data_str:
                        oem_id_index = data_str.index(prefix)
                        ret = data_str[oem_id_index + len(prefix):
                                       oem_id_index + len(prefix) + 4]
                        # Byte 5 is slave address. [7:4] from byte 6 is channel
                        # number, so just pick ret[2] here.
                        ret = (ret[0:2], ret[2])
                        break
        return ret

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

    @ipmitool.execute_ipmi_cmd(NM_STATISTICS_TEMPLATE)
    def _read_power_all(self):
        """Get the power consumption of the whole platform."""
        return self.channel_slave + ' ' + IPMIRAWCMD['read_power_all']

    @ipmitool.execute_ipmi_cmd(NM_STATISTICS_TEMPLATE)
    def _read_temperature_all(self):
        """Get the temperature info of the whole platform."""
        return self.channel_slave + ' ' + IPMIRAWCMD['read_temperature_all']

    def read_power_all(self):
        if self.nm_support:
            return self._read_power_all()

        return {}

    def read_temperature_all(self):
        if self.nm_support:
            return self._read_temperature_all()

        return {}

    def init_node_manager(self):
        if self._init_sensor_agent_process()['ret'] == ['01']:
            return
        # Run sensor initialization agent
        for i in range(CONF.ipmi.node_manager_init_retry):
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

    def node_manager_support(self):
        """Intel Node Manager capability checking

        This function is used to detect if compute node support Intel
        Node Manager or not and parse out the slave address and channel
        number of node manager.
        """
        self.manufacturer_id = self.get_device_id()['Manufacturer_ID']
        if MANUFACTURER_ID_INTEL != self.manufacturer_id:
            # If the manufacturer is not Intel, just set False and return.
            return False

        self.discover_slave_channel()
        support = self._node_manager_get_device_id()['Implemented_firmware']
        # According to Intel Node Manager spec, return value of GET_DEVICE_ID,
        # bits 3 to 0 shows if Intel NM implemented or not.
        if int(support[0], 16) & 0xf != 0:
            return True
        else:
            return False

    def check_node_manager(self):
        """Intel Node Manager init and check

        This function is used to initialize Intel Node Manager and check the
        capability without throwing exception. It's safe to call it on
        non-NodeManager platform.
        """
        try:
            self.init_node_manager()
            has_nm = self.node_manager_support()
        except (nmexcept.NodeManagerException, nmexcept.IPMIException):
            return False
        return has_nm
