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
            assert pollster.CACHE_KEY_CPU in cache
            assert self.instance.name in cache[pollster.CACHE_KEY_CPU]
            # ensure elapsed time between polling cycles is non-zero
            time.sleep(0.001)

        _verify_cpu_metering(1 * (10 ** 6))
        _verify_cpu_metering(3 * (10 ** 6))
        _verify_cpu_metering(2 * (10 ** 6))

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_counters_cache(self):
        self.mox.ReplayAll()

        mgr = manager.AgentManager()
        pollster = cpu.CPUPollster()

        cache = {
            pollster.CACHE_KEY_CPU: {
                self.instance.name: virt_inspector.CPUStats(
                    time=10 ** 6,
                    number=2,
                ),
            },
        }
        counters = list(pollster.get_counters(mgr, cache, self.instance))
        self.assertEquals(len(counters), 1)
        self.assertEquals(counters[0].volume, 10 ** 6)


class TestCPUUtilPollster(base.TestPollsterBase):

    def setUp(self):
        super(TestCPUUtilPollster, self).setUp()

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
        pollster = cpu.CPUUtilPollster()
        pollster.utilization_map = {}  # clear the internal cache

        def _verify_cpu_metering(zero):
            cache = {}
            counters = list(pollster.get_counters(mgr, cache, self.instance))
            self.assertEquals(len(counters), 1)
            self.assertEqual(set([c.name for c in counters]),
                             set(['cpu_util']))
            assert (counters[0].volume == 0.0 if zero else
                    counters[0].volume > 0.0)
            assert pollster.CACHE_KEY_CPU in cache
            assert self.instance.name in cache[pollster.CACHE_KEY_CPU]
            # ensure elapsed time between polling cycles is non-zero
            time.sleep(0.001)

        _verify_cpu_metering(True)
        _verify_cpu_metering(False)
        _verify_cpu_metering(False)

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_counters_cache(self):
        self.mox.ReplayAll()

        mgr = manager.AgentManager()
        pollster = cpu.CPUUtilPollster()
        pollster.utilization_map = {}  # clear the internal cache

        cache = {
            pollster.CACHE_KEY_CPU: {
                self.instance.name: virt_inspector.CPUStats(
                    time=10 ** 6,
                    number=2,
                ),
            },
        }
        counters = list(pollster.get_counters(mgr, cache, self.instance))
        self.assertEquals(len(counters), 1)
        self.assertEquals(counters[0].volume, 0)
