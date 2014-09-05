# Copyright 2014 Intel Corp.
#
# Author: Zhai Edwin <edwin.zhai@intel.com>
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

import binascii

from ceilometer.ipmi.platform import exception as nmexcept
from ceilometer.ipmi.platform import intel_node_manager as node_manager
from ceilometer.tests.ipmi.platform import ipmitool_test_data as test_data


def get_sensor_status_init(parameter=''):
    return (' 01\n', '')


def get_sensor_status_uninit(parameter=''):
    return (' 00\n', '')


def init_sensor_agent(parameter=''):
    return (' 00\n', '')


def sdr_dump(data_file=''):
    if data_file == '':
        raise ValueError("No file specified for ipmitool sdr dump")
    fake_slave_address = '2c'
    fake_channel = '60'
    hexstr = node_manager.INTEL_PREFIX + fake_slave_address + fake_channel
    data = binascii.unhexlify(hexstr)
    with open(data_file, 'wb') as bin_fp:
        bin_fp.write(data)

    return ('', '')


def _execute(funcs, *cmd, **kwargs):

    datas = {
        test_data.device_id_cmd: test_data.device_id,
        test_data.nm_device_id_cmd: test_data.nm_device_id,
        test_data.get_power_cmd: test_data.power_data,
        test_data.get_temperature_cmd: test_data.temperature_data,
        test_data.sdr_info_cmd: test_data.sdr_info,
        test_data.read_sensor_temperature_cmd: test_data.sensor_temperature,
        test_data.read_sensor_voltage_cmd: test_data.sensor_voltage,
        test_data.read_sensor_current_cmd: test_data.sensor_current,
        test_data.read_sensor_fan_cmd: test_data.sensor_fan,
    }

    if cmd[1] == 'sdr' and cmd[2] == 'dump':
        # ipmitool sdr dump /tmp/XXXX
        cmd_str = "".join(cmd[:3])
        par_str = cmd[3]
    else:
        cmd_str = "".join(cmd)
        par_str = ''

    try:
        return datas[cmd_str]
    except KeyError:
        return funcs[cmd_str](par_str)


def execute_with_nm(*cmd, **kwargs):
    """test version of execute on Node Manager platform."""

    funcs = {test_data.sensor_status_cmd: get_sensor_status_init,
             test_data.init_sensor_cmd: init_sensor_agent,
             test_data.sdr_dump_cmd: sdr_dump}

    return _execute(funcs, *cmd, **kwargs)


def execute_without_nm(*cmd, **kwargs):
    """test version of execute on Non-Node Manager platform."""

    funcs = {test_data.sensor_status_cmd: get_sensor_status_uninit,
             test_data.init_sensor_cmd: init_sensor_agent,
             test_data.sdr_dump_cmd: sdr_dump}

    return _execute(funcs, *cmd, **kwargs)


def execute_without_ipmi(*cmd, **kwargs):
    raise nmexcept.IPMIException
