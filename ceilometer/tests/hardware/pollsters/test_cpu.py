#
# Copyright 2013 Intel Corp
#
# Authors: Lianhao Lu <lianhao.lu@intel.com>
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

from ceilometer.hardware.pollsters import cpu
from ceilometer import sample
from ceilometer.tests.hardware.pollsters import base


class TestCPUPollsters(base.TestPollsterBase):
    def test_1min(self):
        self._check_get_samples(cpu.CPULoad1MinPollster,
                                'hardware.cpu.load.1min',
                                0.99, sample.TYPE_GAUGE,
                                expected_unit='process')

    def test_5min(self):
        self._check_get_samples(cpu.CPULoad5MinPollster,
                                'hardware.cpu.load.5min',
                                0.77, sample.TYPE_GAUGE,
                                expected_unit='process')

    def test_15min(self):
        self._check_get_samples(cpu.CPULoad15MinPollster,
                                'hardware.cpu.load.15min',
                                0.55, sample.TYPE_GAUGE,
                                expected_unit='process')
