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

import mock

from ceilometer.ipmi.platform import intel_node_manager as node_manager
from ceilometer.tests.ipmi.platform import fake_utils
from ceilometer import utils

from oslotest import base


class TestNodeManager(base.BaseTestCase):

    def setUp(self):
        super(TestNodeManager, self).setUp()

        utils.execute = mock.Mock(side_effect=fake_utils.execute_with_nm)
        self.nm = node_manager.NodeManager()

    def test_read_power_all(self):
        power = self.nm.read_power_all()

        avg_val = node_manager._hex(power["Average_value"])
        max_val = node_manager._hex(power["Maximum_value"])
        min_val = node_manager._hex(power["Minimum_value"])
        cur_val = node_manager._hex(power["Current_value"])

        self.assertTrue(self.nm.nm_support)
        # see ipmi_test_data.py for raw data
        self.assertEqual(87, cur_val)
        self.assertEqual(3, min_val)
        self.assertEqual(567, max_val)
        self.assertEqual(92, avg_val)

    def test_read_temperature_all(self):
        temperature = self.nm.read_temperature_all()

        avg_val = node_manager._hex(temperature["Average_value"])
        max_val = node_manager._hex(temperature["Maximum_value"])
        min_val = node_manager._hex(temperature["Minimum_value"])
        cur_val = node_manager._hex(temperature["Current_value"])

        self.assertTrue(self.nm.nm_support)
        # see ipmi_test_data.py for raw data
        self.assertEqual(23, cur_val)
        self.assertEqual(22, min_val)
        self.assertEqual(24, max_val)
        self.assertEqual(23, avg_val)


class TestNonNodeManager(base.BaseTestCase):

    def setUp(self):
        super(TestNonNodeManager, self).setUp()

        utils.execute = mock.Mock(side_effect=fake_utils.execute_without_nm)
        self.nm = node_manager.NodeManager()
        self.nm.nm_support = False

    def test_read_power_all(self):
        power = self.nm.read_power_all()

        # Non-Node Manager platform return empty data
        self.assertTrue(power == {})

    def test_read_temperature_all(self):
        temperature = self.nm.read_temperature_all()

        # Non-Node Manager platform return empty data
        self.assertTrue(temperature == {})
