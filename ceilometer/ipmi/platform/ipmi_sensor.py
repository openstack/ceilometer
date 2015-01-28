# Copyright 2014 Intel Corporation.
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

"""IPMI sensor to collect various sensor data of compute node"""

from ceilometer.i18n import _
from ceilometer.ipmi.platform import exception as ipmiexcept
from ceilometer.ipmi.platform import ipmitool

IPMICMD = {"sdr_dump": "sdr dump",
           "sdr_info": "sdr info",
           "sensor_dump": "sdr -v",
           "sensor_dump_temperature": "sdr -v type Temperature",
           "sensor_dump_current": "sdr -v type Current",
           "sensor_dump_fan": "sdr -v type Fan",
           "sensor_dump_voltage": "sdr -v type Voltage"}

# Requires translation of output into dict
DICT_TRANSLATE_TEMPLATE = {"translate": 1}


class IPMISensor(object):
    """The python implementation of IPMI sensor using ipmitool

    The class implements the IPMI sensor to get various sensor data of
    compute node. It uses ipmitool to execute the IPMI command and parse
    the output into dict.
    """
    _inited = False
    _instance = None

    def __new__(cls, *args, **kwargs):
        """Singleton to avoid duplicated initialization."""
        if not cls._instance:
            cls._instance = super(IPMISensor, cls).__new__(cls, *args,
                                                           **kwargs)
        return cls._instance

    def __init__(self):
        if not (self._instance and self._inited):
            self.ipmi_support = False
            self._inited = True

            self.ipmi_support = self.check_ipmi()

    @ipmitool.execute_ipmi_cmd()
    def _get_sdr_info(self):
        """Get the SDR info."""
        return IPMICMD['sdr_info']

    @ipmitool.execute_ipmi_cmd(DICT_TRANSLATE_TEMPLATE)
    def _read_sensor_all(self):
        """Get the sensor data for type."""
        return IPMICMD['sensor_dump']

    @ipmitool.execute_ipmi_cmd(DICT_TRANSLATE_TEMPLATE)
    def _read_sensor_temperature(self):
        """Get the sensor data for Temperature."""
        return IPMICMD['sensor_dump_temperature']

    @ipmitool.execute_ipmi_cmd(DICT_TRANSLATE_TEMPLATE)
    def _read_sensor_voltage(self):
        """Get the sensor data for Voltage."""
        return IPMICMD['sensor_dump_voltage']

    @ipmitool.execute_ipmi_cmd(DICT_TRANSLATE_TEMPLATE)
    def _read_sensor_current(self):
        """Get the sensor data for Current."""
        return IPMICMD['sensor_dump_current']

    @ipmitool.execute_ipmi_cmd(DICT_TRANSLATE_TEMPLATE)
    def _read_sensor_fan(self):
        """Get the sensor data for Fan."""
        return IPMICMD['sensor_dump_fan']

    def read_sensor_any(self, sensor_type=''):
        """Get the sensor data for type."""
        if not self.ipmi_support:
            return {}

        mapping = {'': self._read_sensor_all,
                   'Temperature': self._read_sensor_temperature,
                   'Fan': self._read_sensor_fan,
                   'Voltage': self._read_sensor_voltage,
                   'Current': self._read_sensor_current}

        try:
            return mapping[sensor_type]()
        except KeyError:
            raise ipmiexcept.IPMIException(_('Wrong sensor type'))

    def check_ipmi(self):
        """IPMI capability checking

        This function is used to detect if compute node is IPMI capable
        platform. Just run a simple IPMI command to get SDR info for check.
        """
        try:
            self._get_sdr_info()
        except ipmiexcept.IPMIException:
            return False
        return True
