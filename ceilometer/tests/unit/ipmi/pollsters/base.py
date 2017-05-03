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

import abc

import fixtures
import mock
import six

from ceilometer.agent import manager
from ceilometer import service
from ceilometer.tests import base


@six.add_metaclass(abc.ABCMeta)
class TestPollsterBase(base.BaseTestCase):

    def setUp(self):
        super(TestPollsterBase, self).setUp()
        self.CONF = service.prepare_service([], [])

    def fake_data(self):
        """Fake data used for test."""
        return None

    def fake_sensor_data(self, sensor_type):
        """Fake sensor data used for test."""
        return None

    @abc.abstractmethod
    def make_pollster(self):
        """Produce right pollster for test."""

    def _test_get_samples(self):
        nm = mock.Mock()
        nm.read_inlet_temperature.side_effect = self.fake_data
        nm.read_outlet_temperature.side_effect = self.fake_data
        nm.read_power_all.side_effect = self.fake_data
        nm.read_airflow.side_effect = self.fake_data
        nm.read_cups_index.side_effect = self.fake_data
        nm.read_cups_utilization.side_effect = self.fake_data
        nm.read_sensor_any.side_effect = self.fake_sensor_data
        # We should mock the pollster first before initialize the Manager
        # so that we don't trigger the sudo in pollsters' __init__().
        self.useFixture(fixtures.MockPatch(
            'ceilometer.ipmi.platform.intel_node_manager.NodeManager',
            return_value=nm))

        self.useFixture(fixtures.MockPatch(
            'ceilometer.ipmi.platform.ipmi_sensor.IPMISensor',
            return_value=nm))

        self.mgr = manager.AgentManager(0, self.CONF, ['ipmi'])

        self.pollster = self.make_pollster()

    def _verify_metering(self, length, expected_vol=None, node=None):
        cache = {}
        resources = ['local_host']

        samples = list(self.pollster.get_samples(self.mgr, cache, resources))
        self.assertEqual(length, len(samples))

        if expected_vol:
            self.assertTrue(any(s.volume == expected_vol for s in samples))
        if node:
            self.assertTrue(any(s.resource_metadata['node'] == node
                                for s in samples))
