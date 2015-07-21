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

from ceilometer.network.statistics import flow
from ceilometer import sample
from ceilometer.tests.unit.network import statistics


class TestFlowPollsters(statistics._PollsterTestBase):

    def test_flow_pollster(self):
        self._test_pollster(
            flow.FlowPollster,
            'switch.flow',
            sample.TYPE_GAUGE,
            'flow')

    def test_flow_pollster_duration_seconds(self):
        self._test_pollster(
            flow.FlowPollsterDurationSeconds,
            'switch.flow.duration_seconds',
            sample.TYPE_GAUGE,
            's')

    def test_flow_pollster_duration_nanoseconds(self):
        self._test_pollster(
            flow.FlowPollsterDurationNanoseconds,
            'switch.flow.duration_nanoseconds',
            sample.TYPE_GAUGE,
            'ns')

    def test_flow_pollster_packets(self):
        self._test_pollster(
            flow.FlowPollsterPackets,
            'switch.flow.packets',
            sample.TYPE_CUMULATIVE,
            'packet')

    def test_flow_pollster_bytes(self):
        self._test_pollster(
            flow.FlowPollsterBytes,
            'switch.flow.bytes',
            sample.TYPE_CUMULATIVE,
            'B')
