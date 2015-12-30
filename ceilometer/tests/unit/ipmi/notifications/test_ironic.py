#
# Copyright 2014 Red Hat, Inc
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
"""Tests for producing IPMI sample messages from notification events.
"""

import mock
from oslotest import base

from ceilometer.ipmi.notifications import ironic as ipmi
from ceilometer import sample
from ceilometer.tests.unit.ipmi.notifications import ipmi_test_data


class TestNotifications(base.BaseTestCase):

    def test_ipmi_temperature_notification(self):
        """Test IPMI Temperature sensor data.

        Based on the above ipmi_testdata the expected sample for a single
        temperature reading has::

        * a resource_id composed from the node_uuid Sensor ID
        * a name composed from 'hardware.ipmi.' and 'temperature'
        * a volume from the first chunk of the Sensor Reading
        * a unit from the last chunk of the Sensor Reading
        * some readings are skipped if the value is 'Disabled'
        * metatata with the node id
        """
        processor = ipmi.TemperatureSensorNotification(None)
        counters = dict([(counter.resource_id, counter) for counter in
                         processor.process_notification(
                             ipmi_test_data.SENSOR_DATA)])

        self.assertEqual(10, len(counters),
                         'expected 10 temperature readings')
        resource_id = (
            'f4982fd2-2f2b-4bb5-9aff-48aac801d1ad-dimm_gh_vr_temp_(0x3b)'
        )
        test_counter = counters[resource_id]
        self.assertEqual(26.0, test_counter.volume)
        self.assertEqual('C', test_counter.unit)
        self.assertEqual(sample.TYPE_GAUGE, test_counter.type)
        self.assertEqual('hardware.ipmi.temperature', test_counter.name)
        self.assertEqual('hardware.ipmi.metrics.update',
                         test_counter.resource_metadata['event_type'])
        self.assertEqual('f4982fd2-2f2b-4bb5-9aff-48aac801d1ad',
                         test_counter.resource_metadata['node'])

    def test_ipmi_current_notification(self):
        """Test IPMI Current sensor data.

        A single current reading is effectively the same as temperature,
        modulo "current".
        """
        processor = ipmi.CurrentSensorNotification(None)
        counters = dict([(counter.resource_id, counter) for counter in
                         processor.process_notification(
                             ipmi_test_data.SENSOR_DATA)])

        self.assertEqual(1, len(counters), 'expected 1 current reading')
        resource_id = (
            'f4982fd2-2f2b-4bb5-9aff-48aac801d1ad-avg_power_(0x2e)'
        )
        test_counter = counters[resource_id]
        self.assertEqual(130.0, test_counter.volume)
        self.assertEqual('W', test_counter.unit)
        self.assertEqual(sample.TYPE_GAUGE, test_counter.type)
        self.assertEqual('hardware.ipmi.current', test_counter.name)

    def test_ipmi_fan_notification(self):
        """Test IPMI Fan sensor data.

        A single fan reading is effectively the same as temperature,
        modulo "fan".
        """
        processor = ipmi.FanSensorNotification(None)
        counters = dict([(counter.resource_id, counter) for counter in
                         processor.process_notification(
                             ipmi_test_data.SENSOR_DATA)])

        self.assertEqual(12, len(counters), 'expected 12 fan readings')
        resource_id = (
            'f4982fd2-2f2b-4bb5-9aff-48aac801d1ad-fan_4a_tach_(0x46)'
        )
        test_counter = counters[resource_id]
        self.assertEqual(6900.0, test_counter.volume)
        self.assertEqual('RPM', test_counter.unit)
        self.assertEqual(sample.TYPE_GAUGE, test_counter.type)
        self.assertEqual('hardware.ipmi.fan', test_counter.name)

    def test_ipmi_voltage_notification(self):
        """Test IPMI Voltage sensor data.

        A single voltage reading is effectively the same as temperature,
        modulo "voltage".
        """
        processor = ipmi.VoltageSensorNotification(None)
        counters = dict([(counter.resource_id, counter) for counter in
                         processor.process_notification(
                             ipmi_test_data.SENSOR_DATA)])

        self.assertEqual(4, len(counters), 'expected 4 volate readings')
        resource_id = (
            'f4982fd2-2f2b-4bb5-9aff-48aac801d1ad-planar_vbat_(0x1c)'
        )
        test_counter = counters[resource_id]
        self.assertEqual(3.137, test_counter.volume)
        self.assertEqual('V', test_counter.unit)
        self.assertEqual(sample.TYPE_GAUGE, test_counter.type)
        self.assertEqual('hardware.ipmi.voltage', test_counter.name)

    def test_disabed_skips_metric(self):
        """Test that a meter which a disabled volume is skipped."""
        processor = ipmi.TemperatureSensorNotification(None)
        counters = dict([(counter.resource_id, counter) for counter in
                         processor.process_notification(
                             ipmi_test_data.SENSOR_DATA)])

        self.assertEqual(10, len(counters),
                         'expected 10 temperature readings')

        resource_id = (
            'f4982fd2-2f2b-4bb5-9aff-48aac801d1ad-mezz_card_temp_(0x35)'
        )

        self.assertNotIn(resource_id, counters)

    def test_empty_payload_no_metrics_success(self):
        processor = ipmi.TemperatureSensorNotification(None)
        counters = dict([(counter.resource_id, counter) for counter in
                         processor.process_notification(
                             ipmi_test_data.EMPTY_PAYLOAD)])

        self.assertEqual(0, len(counters), 'expected 0 readings')

    @mock.patch('ceilometer.ipmi.notifications.ironic.LOG')
    def test_missing_sensor_data(self, mylog):
        processor = ipmi.TemperatureSensorNotification(None)

        messages = []
        mylog.warning = lambda *args: messages.extend(args)

        list(processor.process_notification(ipmi_test_data.MISSING_SENSOR))

        self.assertEqual(
            'invalid sensor data for '
            'f4982fd2-2f2b-4bb5-9aff-48aac801d1ad-pci_riser_1_temp_(0x33): '
            "missing 'Sensor Reading' in payload",
            messages[0]
        )

    @mock.patch('ceilometer.ipmi.notifications.ironic.LOG')
    def test_sensor_data_malformed(self, mylog):
        processor = ipmi.TemperatureSensorNotification(None)

        messages = []
        mylog.warning = lambda *args: messages.extend(args)

        list(processor.process_notification(ipmi_test_data.BAD_SENSOR))

        self.assertEqual(
            'invalid sensor data for '
            'f4982fd2-2f2b-4bb5-9aff-48aac801d1ad-pci_riser_1_temp_(0x33): '
            'unable to parse sensor reading: some bad stuff',
            messages[0]
        )

    @mock.patch('ceilometer.ipmi.notifications.ironic.LOG')
    def test_missing_node_uuid(self, mylog):
        """Test for desired error message when 'node_uuid' missing.

        Presumably this will never happen given the way the data
        is created, but better defensive than dead.
        """
        processor = ipmi.TemperatureSensorNotification(None)

        messages = []
        mylog.warning = lambda *args: messages.extend(args)

        list(processor.process_notification(ipmi_test_data.NO_NODE_ID))

        self.assertEqual(
            'invalid sensor data for missing id: missing key in payload: '
            "'node_uuid'",
            messages[0]
        )

    @mock.patch('ceilometer.ipmi.notifications.ironic.LOG')
    def test_missing_sensor_id(self, mylog):
        """Test for desired error message when 'Sensor ID' missing."""
        processor = ipmi.TemperatureSensorNotification(None)

        messages = []
        mylog.warning = lambda *args: messages.extend(args)

        list(processor.process_notification(ipmi_test_data.NO_SENSOR_ID))

        self.assertEqual(
            'invalid sensor data for missing id: missing key in payload: '
            "'Sensor ID'",
            messages[0]
        )
