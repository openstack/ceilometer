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

from ceilometer.hardware.pollsters import net
from ceilometer import sample
from ceilometer.tests.hardware.pollsters import base


class TestNetPollsters(base.TestPollsterBase):
    def test_incoming(self):
        self._check_get_samples(net.IncomingBytesPollster,
                                'hardware.network.incoming.bytes',
                                90, sample.TYPE_CUMULATIVE,
                                expected_unit='B')

    def test_outgoing(self):
        self._check_get_samples(net.OutgoingBytesPollster,
                                'hardware.network.outgoing.bytes',
                                80, sample.TYPE_CUMULATIVE,
                                expected_unit='B')

    def test_error(self):
        self._check_get_samples(net.OutgoingErrorsPollster,
                                'hardware.network.outgoing.errors',
                                1, sample.TYPE_CUMULATIVE,
                                expected_unit='packet')
