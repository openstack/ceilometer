# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
# Copyright © 2012 Red Hat, Inc
#
# Author: Julien Danjou <julien@danjou.info>
# Author: Eoghan Glynn <eglynn@redhat.com>
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

import time

import mock

from ceilometer.compute import manager
from ceilometer.compute.pollsters import cpu
from ceilometer.compute.virt import inspector as virt_inspector

from . import base


class TestCPUPollster(base.TestPollsterBase):

    def setUp(self):
        super(TestCPUPollster, self).setUp()

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_counters(self):
        self.inspector.inspect_cpus(self.instance.name).AndReturn(
            virt_inspector.CPUStats(time=1 * (10 ** 6), number=2))
        self.inspector.inspect_cpus(self.instance.name).AndReturn(
            virt_inspector.CPUStats(time=3 * (10 ** 6), number=2))
        # cpu_time resets on instance restart
        self.inspector.inspect_cpus(self.instance.name).AndReturn(
            virt_inspector.CPUStats(time=2 * (10 ** 6), number=2))
        self.mox.ReplayAll()

        mgr = manager.AgentManager()
        pollster = cpu.CPUPollster()

        def _verify_cpu_metering(expected_time):
            cache = {}
            counters = list(pollster.get_counters(mgr, cache, self.instance))
            self.assertEquals(len(counters), 1)
            self.assertEqual(set([c.name for c in counters]),
                             set(['cpu']))
            assert counters[0].volume == expected_time
            self.assertEquals(counters[0].resource_metadata.get('cpu_number'),
                              2)
            # ensure elapsed time between polling cycles is non-zero
            time.sleep(0.001)

        _verify_cpu_metering(1 * (10 ** 6))
        _verify_cpu_metering(3 * (10 ** 6))
        _verify_cpu_metering(2 * (10 ** 6))

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_counters_no_caching(self):
        self.inspector.inspect_cpus(self.instance.name).AndReturn(
            virt_inspector.CPUStats(time=1 * (10 ** 6), number=2))
        self.mox.ReplayAll()

        mgr = manager.AgentManager()
        pollster = cpu.CPUPollster()

        cache = {}
        counters = list(pollster.get_counters(mgr, cache, self.instance))
        self.assertEquals(len(counters), 1)
        self.assertEquals(counters[0].volume, 10 ** 6)
        self.assertEquals(len(cache), 0)
