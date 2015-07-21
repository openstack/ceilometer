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
from oslotest import base

from ceilometer.ipmi.platform import ipmi_sensor
from ceilometer.tests.unit.ipmi.platform import fake_utils
from ceilometer import utils


class TestIPMISensor(base.BaseTestCase):

    def setUp(self):
        super(TestIPMISensor, self).setUp()

        utils.execute = mock.Mock(side_effect=fake_utils.execute_with_nm_v2)
        self.ipmi = ipmi_sensor.IPMISensor()

    @classmethod
    def tearDownClass(cls):
        # reset inited to force an initialization of singleton for next test
        ipmi_sensor.IPMISensor()._inited = False
        super(TestIPMISensor, cls).tearDownClass()

    def test_read_sensor_temperature(self):
        sensors = self.ipmi.read_sensor_any('Temperature')

        self.assertTrue(self.ipmi.ipmi_support)
        # only temperature data returned.
        self.assertIn('Temperature', sensors)
        self.assertEqual(1, len(sensors))

        # 4 sensor data in total, ignore 1 without 'Sensor Reading'.
        # Check ceilometer/tests/ipmi/platform/ipmi_test_data.py
        self.assertEqual(3, len(sensors['Temperature']))
        sensor = sensors['Temperature']['BB P1 VR Temp (0x20)']
        self.assertEqual('25 (+/- 0) degrees C', sensor['Sensor Reading'])

    def test_read_sensor_voltage(self):
        sensors = self.ipmi.read_sensor_any('Voltage')

        # only voltage data returned.
        self.assertIn('Voltage', sensors)
        self.assertEqual(1, len(sensors))

        # 4 sensor data in total, ignore 1 without 'Sensor Reading'.
        # Check ceilometer/tests/ipmi/platform/ipmi_test_data.py
        self.assertEqual(3, len(sensors['Voltage']))
        sensor = sensors['Voltage']['BB +5.0V (0xd1)']
        self.assertEqual('4.959 (+/- 0) Volts', sensor['Sensor Reading'])

    def test_read_sensor_current(self):
        sensors = self.ipmi.read_sensor_any('Current')

        # only Current data returned.
        self.assertIn('Current', sensors)
        self.assertEqual(1, len(sensors))

        # 2 sensor data in total.
        # Check ceilometer/tests/ipmi/platform/ipmi_test_data.py
        self.assertEqual(2, len(sensors['Current']))
        sensor = sensors['Current']['PS1 Curr Out % (0x58)']
        self.assertEqual('11 (+/- 0) unspecified', sensor['Sensor Reading'])

    def test_read_sensor_fan(self):
        sensors = self.ipmi.read_sensor_any('Fan')

        # only Fan data returned.
        self.assertIn('Fan', sensors)
        self.assertEqual(1, len(sensors))

        # 2 sensor data in total.
        # Check ceilometer/tests/ipmi/platform/ipmi_test_data.py
        self.assertEqual(4, len(sensors['Fan']))
        sensor = sensors['Fan']['System Fan 2 (0x32)']
        self.assertEqual('4704 (+/- 0) RPM', sensor['Sensor Reading'])


class TestNonIPMISensor(base.BaseTestCase):

    def setUp(self):
        super(TestNonIPMISensor, self).setUp()

        utils.execute = mock.Mock(side_effect=fake_utils.execute_without_ipmi)
        self.ipmi = ipmi_sensor.IPMISensor()

    @classmethod
    def tearDownClass(cls):
        # reset inited to force an initialization of singleton for next test
        ipmi_sensor.IPMISensor()._inited = False
        super(TestNonIPMISensor, cls).tearDownClass()

    def test_read_sensor_temperature(self):
        sensors = self.ipmi.read_sensor_any('Temperature')

        self.assertFalse(self.ipmi.ipmi_support)
        # Non-IPMI platform return empty data
        self.assertEqual({}, sensors)

    def test_read_sensor_voltage(self):
        sensors = self.ipmi.read_sensor_any('Voltage')

        # Non-IPMI platform return empty data
        self.assertEqual({}, sensors)

    def test_read_sensor_current(self):
        sensors = self.ipmi.read_sensor_any('Current')

        # Non-IPMI platform return empty data
        self.assertEqual({}, sensors)

    def test_read_sensor_fan(self):
        sensors = self.ipmi.read_sensor_any('Fan')

        # Non-IPMI platform return empty data
        self.assertEqual({}, sensors)
