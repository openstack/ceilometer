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

from ceilometer.hardware.pollsters import system
from ceilometer import sample
from ceilometer.tests.hardware.pollsters import base


class TestSystemPollsters(base.TestPollsterBase):
    def test_cpu_idle(self):
        self._check_get_samples(system.SystemCpuIdlePollster,
                                'hardware.system_stats.cpu.idle',
                                62, sample.TYPE_GAUGE,
                                expected_unit='%')

    def test_io_outgoing(self):
        self._check_get_samples(system.SystemIORawSentPollster,
                                'hardware.system_stats.io.outgoing.blocks',
                                100, sample.TYPE_CUMULATIVE,
                                expected_unit='blocks')

    def test_io_incoming(self):
        self._check_get_samples(system.SystemIORawReceivedPollster,
                                'hardware.system_stats.io.incoming.blocks',
                                120, sample.TYPE_CUMULATIVE,
                                expected_unit='blocks')
