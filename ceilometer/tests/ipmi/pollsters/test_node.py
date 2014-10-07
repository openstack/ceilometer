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
from oslo.config import cfg

from ceilometer.ipmi.pollsters import node
from ceilometer.tests.ipmi.pollsters import base


CONF = cfg.CONF
CONF.import_opt('host', 'ceilometer.service')


class TestPowerPollster(base.TestPollsterBase):

    def fake_data(self):
        # data after parsing Intel Node Manager output
        return {"Current_value": ['13', '00']}

    def fake_sensor_data(self, sensor_type):
        # No use for this test
        return None

    def make_pollster(self):
        return node.PowerPollster()

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_samples(self):
        self._test_get_samples()

        # only one sample, and value is 19(0x13 as current_value)
        self._verify_metering(1, 19, CONF.host)


class TestTemperaturePollster(base.TestPollsterBase):

    def fake_data(self):
        # data after parsing Intel Node Manager output
        return {"Current_value": ['23', '00']}

    def fake_sensor_data(self, sensor_type):
        # No use for this test
        return None

    def make_pollster(self):
        return node.TemperaturePollster()

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_samples(self):
        self._test_get_samples()

        # only one sample, and value is 35(0x23 as current_value)
        self._verify_metering(1, 35, CONF.host)
