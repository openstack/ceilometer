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

import mock

from ceilometer.ipmi.pollsters import sensor
from ceilometer.tests.unit.ipmi.notifications import ipmi_test_data
from ceilometer.tests.unit.ipmi.pollsters import base

TEMPERATURE_SENSOR_DATA = {
    'Temperature': ipmi_test_data.TEMPERATURE_DATA
}

CURRENT_SENSOR_DATA = {
    'Current': ipmi_test_data.CURRENT_DATA
}

FAN_SENSOR_DATA = {
    'Fan': ipmi_test_data.FAN_DATA
}

VOLTAGE_SENSOR_DATA = {
    'Voltage': ipmi_test_data.VOLTAGE_DATA
}

MISSING_SENSOR_DATA = ipmi_test_data.MISSING_SENSOR['payload']['payload']
MALFORMED_SENSOR_DATA = ipmi_test_data.BAD_SENSOR['payload']['payload']
MISSING_ID_SENSOR_DATA = ipmi_test_data.NO_SENSOR_ID['payload']['payload']


class TestTemperatureSensorPollster(base.TestPollsterBase):

    def fake_sensor_data(self, sensor_type):
        return TEMPERATURE_SENSOR_DATA

    def make_pollster(self):
        return sensor.TemperatureSensorPollster(self.CONF)

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_samples(self):
        self._test_get_samples()

        self._verify_metering(10, float(32), self.CONF.host)


class TestMissingSensorData(base.TestPollsterBase):

    def fake_sensor_data(self, sensor_type):
        return MISSING_SENSOR_DATA

    def make_pollster(self):
        return sensor.TemperatureSensorPollster(self.CONF)

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_samples(self):
        self._test_get_samples()
        self._verify_metering(0)


class TestMalformedSensorData(base.TestPollsterBase):

    def fake_sensor_data(self, sensor_type):
        return MALFORMED_SENSOR_DATA

    def make_pollster(self):
        return sensor.TemperatureSensorPollster(self.CONF)

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_samples(self):
        self._test_get_samples()
        self._verify_metering(0)


class TestMissingSensorId(base.TestPollsterBase):

    def fake_sensor_data(self, sensor_type):
        return MISSING_ID_SENSOR_DATA

    def make_pollster(self):
        return sensor.TemperatureSensorPollster(self.CONF)

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_samples(self):
        self._test_get_samples()
        self._verify_metering(0)


class TestFanSensorPollster(base.TestPollsterBase):

    def fake_sensor_data(self, sensor_type):
        return FAN_SENSOR_DATA

    def make_pollster(self):
        return sensor.FanSensorPollster(self.CONF)

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_samples(self):
        self._test_get_samples()

        self._verify_metering(12, float(7140), self.CONF.host)


class TestCurrentSensorPollster(base.TestPollsterBase):

    def fake_sensor_data(self, sensor_type):
        return CURRENT_SENSOR_DATA

    def make_pollster(self):
        return sensor.CurrentSensorPollster(self.CONF)

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_samples(self):
        self._test_get_samples()

        self._verify_metering(1, float(130), self.CONF.host)


class TestVoltageSensorPollster(base.TestPollsterBase):

    def fake_sensor_data(self, sensor_type):
        return VOLTAGE_SENSOR_DATA

    def make_pollster(self):
        return sensor.VoltageSensorPollster(self.CONF)

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_samples(self):
        self._test_get_samples()

        self._verify_metering(4, float(3.309), self.CONF.host)
