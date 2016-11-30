# Copyright 2014 Intel
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

from oslo_log import log

from ceilometer.agent import plugin_base
from ceilometer.i18n import _
from ceilometer.ipmi.notifications import ironic as parser
from ceilometer.ipmi.platform import exception as ipmiexcept
from ceilometer.ipmi.platform import ipmi_sensor
from ceilometer import sample

LOG = log.getLogger(__name__)


class InvalidSensorData(ValueError):
    pass


class SensorPollster(plugin_base.PollsterBase):
    METRIC = None

    def setup_environment(self):
        super(SensorPollster, self).setup_environment()
        self.ipmi = ipmi_sensor.IPMISensor()
        self.polling_failures = 0

        # Do not load this extension if no IPMI support
        if not self.ipmi.ipmi_support:
            raise plugin_base.ExtensionLoadError()

    @property
    def default_discovery(self):
        return 'local_node'

    @staticmethod
    def _get_sensor_types(data, sensor_type):
        try:
            return (sensor_type_data for _, sensor_type_data
                    in data[sensor_type].items())
        except KeyError:
            return []

    def get_samples(self, manager, cache, resources):
        # Only one resource for IPMI pollster
        try:
            stats = self.ipmi.read_sensor_any(self.METRIC)
        except ipmiexcept.IPMIException:
            self.polling_failures += 1
            LOG.warning(_(
                'Polling %(mtr)s sensor failed for %(cnt)s times!')
                % ({'mtr': self.METRIC,
                    'cnt': self.polling_failures}))
            if 0 <= self.conf.ipmi.polling_retry < self.polling_failures:
                LOG.warning(_('Pollster for %s is disabled!') % self.METRIC)
                raise plugin_base.PollsterPermanentError(resources)
            else:
                return

        self.polling_failures = 0

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
                'host': self.conf.host,
                'sensor-id': parser.transform_id(sensor_id)
            }

            metadata = {
                'node': self.conf.host
            }

            yield sample.Sample(
                name='hardware.ipmi.%s' % self.METRIC.lower(),
                type=sample.TYPE_GAUGE,
                unit=unit,
                volume=volume,
                user_id=None,
                project_id=None,
                resource_id=resource_id,
                resource_metadata=metadata)


class TemperatureSensorPollster(SensorPollster):
    METRIC = 'Temperature'


class CurrentSensorPollster(SensorPollster):
    METRIC = 'Current'


class FanSensorPollster(SensorPollster):
    METRIC = 'Fan'


class VoltageSensorPollster(SensorPollster):
    METRIC = 'Voltage'
