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

from ceilometer.network.statistics import port
from ceilometer import sample
from ceilometer.tests.unit.network import statistics


class TestPortPollsters(statistics._PollsterTestBase):

    def test_port_pollster(self):
        self._test_pollster(
            port.PortPollster,
            'switch.port',
            sample.TYPE_GAUGE,
            'port')

    def test_port_pollster_uptime(self):
        self._test_pollster(
            port.PortPollsterUptime,
            'switch.port.uptime',
            sample.TYPE_GAUGE,
            's')

    def test_port_pollster_receive_packets(self):
        self._test_pollster(
            port.PortPollsterReceivePackets,
            'switch.port.receive.packets',
            sample.TYPE_CUMULATIVE,
            'packet')

    def test_port_pollster_transmit_packets(self):
        self._test_pollster(
            port.PortPollsterTransmitPackets,
            'switch.port.transmit.packets',
            sample.TYPE_CUMULATIVE,
            'packet')

    def test_port_pollster_receive_bytes(self):
        self._test_pollster(
            port.PortPollsterReceiveBytes,
            'switch.port.receive.bytes',
            sample.TYPE_CUMULATIVE,
            'B')

    def test_port_pollster_transmit_bytes(self):
        self._test_pollster(
            port.PortPollsterTransmitBytes,
            'switch.port.transmit.bytes',
            sample.TYPE_CUMULATIVE,
            'B')

    def test_port_pollster_receive_drops(self):
        self._test_pollster(
            port.PortPollsterReceiveDrops,
            'switch.port.receive.drops',
            sample.TYPE_CUMULATIVE,
            'packet')

    def test_port_pollster_transmit_drops(self):
        self._test_pollster(
            port.PortPollsterTransmitDrops,
            'switch.port.transmit.drops',
            sample.TYPE_CUMULATIVE,
            'packet')

    def test_port_pollster_receive_errors(self):
        self._test_pollster(
            port.PortPollsterReceiveErrors,
            'switch.port.receive.errors',
            sample.TYPE_CUMULATIVE,
            'packet')

    def test_port_pollster_transmit_errors(self):
        self._test_pollster(
            port.PortPollsterTransmitErrors,
            'switch.port.transmit.errors',
            sample.TYPE_CUMULATIVE,
            'packet')

    def test_port_pollster_receive_frame_errors(self):
        self._test_pollster(
            port.PortPollsterReceiveFrameErrors,
            'switch.port.receive.frame_error',
            sample.TYPE_CUMULATIVE,
            'packet')

    def test_port_pollster_receive_overrun_errors(self):
        self._test_pollster(
            port.PortPollsterReceiveOverrunErrors,
            'switch.port.receive.overrun_error',
            sample.TYPE_CUMULATIVE,
            'packet')

    def test_port_pollster_receive_crc_errors(self):
        self._test_pollster(
            port.PortPollsterReceiveCRCErrors,
            'switch.port.receive.crc_error',
            sample.TYPE_CUMULATIVE,
            'packet')

    def test_port_pollster_collision_count(self):
        self._test_pollster(
            port.PortPollsterCollisionCount,
            'switch.port.collision.count',
            sample.TYPE_CUMULATIVE,
            'packet')
