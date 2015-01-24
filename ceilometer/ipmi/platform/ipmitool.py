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

"""Utils to run ipmitool for data collection"""
from oslo_concurrency import processutils

from ceilometer.i18n import _
from ceilometer.ipmi.platform import exception as ipmiexcept
from ceilometer import utils


# Following 2 functions are copied from ironic project to handle ipmitool's
# sensor data output. Need code clean and sharing in future.
# Check ironic/drivers/modules/ipmitool.py


def _get_sensor_type(sensor_data_dict):
    # Have only three sensor type name IDs: 'Sensor Type (Analog)'
    # 'Sensor Type (Discrete)' and 'Sensor Type (Threshold)'

    for key in ('Sensor Type (Analog)', 'Sensor Type (Discrete)',
                'Sensor Type (Threshold)'):
        try:
            return sensor_data_dict[key].split(' ', 1)[0]
        except KeyError:
            continue

    raise ipmiexcept.IPMIException(_("parse IPMI sensor data failed,"
                                     "unknown sensor type"))


def _process_sensor(sensor_data):
    sensor_data_fields = sensor_data.split('\n')
    sensor_data_dict = {}
    for field in sensor_data_fields:
        if not field:
            continue
        kv_value = field.split(':')
        if len(kv_value) != 2:
            continue
        sensor_data_dict[kv_value[0].strip()] = kv_value[1].strip()

    return sensor_data_dict


def _translate_output(output):
    """Translate the return value into JSON dict

    :param output: output of the execution of IPMI command(sensor reading)
    """
    sensors_data_dict = {}

    sensors_data_array = output.split('\n\n')
    for sensor_data in sensors_data_array:
        sensor_data_dict = _process_sensor(sensor_data)
        if not sensor_data_dict:
            continue

        sensor_type = _get_sensor_type(sensor_data_dict)

        # ignore the sensors which have no current 'Sensor Reading' data
        sensor_id = sensor_data_dict['Sensor ID']
        if 'Sensor Reading' in sensor_data_dict:
            sensors_data_dict.setdefault(sensor_type,
                                         {})[sensor_id] = sensor_data_dict

    # get nothing, no valid sensor data
    if not sensors_data_dict:
        raise ipmiexcept.IPMIException(_("parse IPMI sensor data failed,"
                                         "No data retrieved from given input"))
    return sensors_data_dict


def _parse_output(output, template):
    """Parse the return value of IPMI command into dict

    :param output: output of the execution of IPMI command
    :param template: a dict that contains the expected items of
                         IPMI command and its length.
    """
    ret = {}
    index = 0
    if not (output and template):
        return ret

    if "translate" in template:
        ret = _translate_output(output)
    else:
        output_list = output.strip().replace('\n', '').split(' ')
        if sum(template.values()) != len(output_list):
            raise ipmiexcept.IPMIException(_("ipmitool output "
                                             "length mismatch"))
        for item in template.items():
            index_end = index + item[1]
            update_value = output_list[index: index_end]
            ret[item[0]] = update_value
            index = index_end
    return ret


def execute_ipmi_cmd(template=None):
    """Decorator for the execution of IPMI command.

    It parses the output of IPMI command into dictionary.
    """

    template = template or []

    def _execute_ipmi_cmd(f):
        def _execute(self, **kwargs):
            args = ['ipmitool']
            command = f(self, **kwargs)
            args.extend(command.split(" "))
            try:
                (out, __) = utils.execute(*args, run_as_root=True)
            except processutils.ProcessExecutionError:
                raise ipmiexcept.IPMIException(_("running ipmitool failure"))
            return _parse_output(out, template)
        return _execute

    return _execute_ipmi_cmd
