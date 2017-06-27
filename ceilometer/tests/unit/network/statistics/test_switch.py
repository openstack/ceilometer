#
# Copyright 2014 NEC Corporation.  All rights reserved.
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

from ceilometer.network.statistics import switch
from ceilometer import sample
from ceilometer.tests.unit.network import statistics


class TestSwitchPollster(statistics._PollsterTestBase):

    def test_switch_pollster(self):
        self._test_pollster(
            switch.SWPollster,
            'switch',
            sample.TYPE_GAUGE,
            'switch')

    def test_switch_pollster_ports(self):
        self._test_pollster(
            switch.SwitchPollsterPorts,
            'switch.ports',
            sample.TYPE_GAUGE,
            'ports')
