# Copyright 2014 Intel Corp.
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

from ceilometer.ipmi.platform import exception as nmexcept
from ceilometer.tests.unit.ipmi.platform import ipmitool_test_data as test_data


def get_sensor_status_init(parameter=''):
    return (' 01\n', '')


def get_sensor_status_uninit(parameter=''):
    return (' 00\n', '')


def init_sensor_agent(parameter=''):
    return (' 00\n', '')


def execute(*cmd, **kwargs):

    datas = {
        test_data.sdr_info_cmd: test_data.sdr_info,
        test_data.read_sensor_temperature_cmd: test_data.sensor_temperature,
        test_data.read_sensor_voltage_cmd: test_data.sensor_voltage,
        test_data.read_sensor_current_cmd: test_data.sensor_current,
        test_data.read_sensor_fan_cmd: test_data.sensor_fan,
    }

    cmd_str = "".join(cmd)
    return datas[cmd_str]


def execute_without_ipmi(*cmd, **kwargs):
    raise nmexcept.IPMIException
