# Copyright 2014 Intel
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

from oslo.config import cfg
from oslo.utils import timeutils

from ceilometer.ipmi.notifications import ironic as parser
from ceilometer.ipmi.platform import ipmi_sensor
from ceilometer import plugin
from ceilometer import sample

CONF = cfg.CONF
CONF.import_opt('host', 'ceilometer.service')


class InvalidSensorData(ValueError):
    pass


class SensorPollster(plugin.PollsterBase):

    METRIC = None

    def __init__(self):
        self.ipmi = ipmi_sensor.IPMISensor()

    @property
    def default_discovery(self):
        return None

    def _get_sensor_types(self, data, sensor_type):
        try:
            return (sensor_type_data for _, sensor_type_data
                    in data[sensor_type].items())
        except KeyError:
            return []

    def get_samples(self, manager, cache, resources):
        stats = self.ipmi.read_sensor_any(self.METRIC)

        sensor_type_data = self._get_sensor_types(stats, self.METRIC)

        for sensor_data in sensor_type_data:
            # Continue if sensor_data is not parseable.
            try:
                sensor_reading = sensor_data['Sensor Reading']
                sensor_id = sensor_data['Sensor ID']
            except KeyError:
                continue

            if not parser.validate_reading(sensor_reading):
                continue

            try:
                volume, unit = parser.parse_reading(sensor_reading)
            except parser.InvalidSensorData:
                continue

            resource_id = '%(host)s-%(sensor-id)s' % {
                'host': CONF.host,
                'sensor-id': parser.transform_id(sensor_id)
            }

            metadata = {
                'node': CONF.host
            }

            yield sample.Sample(
                name='hardware.ipmi.%s' % self.METRIC.lower(),
                type=sample.TYPE_GAUGE,
                unit=unit,
                volume=volume,
                user_id=None,
                project_id=None,
                resource_id=resource_id,
                timestamp=timeutils.utcnow().isoformat(),
                resource_metadata=metadata)


class TemperatureSensorPollster(SensorPollster):
    METRIC = 'Temperature'


class CurrentSensorPollster(SensorPollster):
    METRIC = 'Current'


class FanSensorPollster(SensorPollster):
    METRIC = 'Fan'


class VoltageSensorPollster(SensorPollster):
    METRIC = 'Voltage'
