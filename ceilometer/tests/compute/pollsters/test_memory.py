# Copyright (c) 2014 VMware, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mock

from ceilometer.compute import manager
from ceilometer.compute.pollsters import memory
from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.tests.compute.pollsters import base


class TestMemoryPollster(base.TestPollsterBase):

    def setUp(self):
        super(TestMemoryPollster, self).setUp()

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_samples(self):
        next_value = iter((
            virt_inspector.MemoryUsageStats(usage=1.0),
            virt_inspector.MemoryUsageStats(usage=2.0),
        ))

        def inspect_memory_usage(instance, duration):
            return next(next_value)

        (self.inspector.
         inspect_memory_usage) = mock.Mock(side_effect=inspect_memory_usage)

        mgr = manager.AgentManager()
        pollster = memory.MemoryUsagePollster()

        def _verify_memory_metering(expected_memory_mb):
            cache = {}
            samples = list(pollster.get_samples(mgr, cache, [self.instance]))
            self.assertEqual(1, len(samples))
            self.assertEqual(set(['memory.usage']),
                             set([s.name for s in samples]))
            self.assertEqual(expected_memory_mb, samples[0].volume)

        _verify_memory_metering(1.0)
        _verify_memory_metering(2.0)
