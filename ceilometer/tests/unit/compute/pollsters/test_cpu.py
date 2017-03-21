#
# Copyright 2012 eNovance <licensing@enovance.com>
# Copyright 2012 Red Hat, Inc
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

from ceilometer.agent import manager
from ceilometer.compute.pollsters import instance_stats
from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.tests.unit.compute.pollsters import base


class TestCPUPollster(base.TestPollsterBase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_samples(self):
        self._mock_inspect_instance(
            virt_inspector.InstanceStats(cpu_time=1 * (10 ** 6), cpu_number=2),
            virt_inspector.InstanceStats(cpu_time=3 * (10 ** 6), cpu_number=2),
            # cpu_time resets on instance restart
            virt_inspector.InstanceStats(cpu_time=2 * (10 ** 6), cpu_number=2),
        )

        mgr = manager.AgentManager(0, self.CONF)
        pollster = instance_stats.CPUPollster(self.CONF)

        def _verify_cpu_metering(expected_time):
            cache = {}
            samples = list(pollster.get_samples(mgr, cache, [self.instance]))
            self.assertEqual(1, len(samples))
            self.assertEqual(set(['cpu']), set([s.name for s in samples]))
            self.assertEqual(expected_time, samples[0].volume)
            self.assertEqual(2, samples[0].resource_metadata.get('cpu_number'))
            # ensure elapsed time between polling cycles is non-zero
            time.sleep(0.001)

        _verify_cpu_metering(1 * (10 ** 6))
        _verify_cpu_metering(3 * (10 ** 6))
        _verify_cpu_metering(2 * (10 ** 6))

    # the following apply to all instance resource pollsters but are tested
    # here alone.

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_metadata(self):
        mgr = manager.AgentManager(0, self.CONF)
        pollster = instance_stats.CPUPollster(self.CONF)
        samples = list(pollster.get_samples(mgr, {}, [self.instance]))
        self.assertEqual(1, len(samples))
        self.assertEqual(1, samples[0].resource_metadata['vcpus'])
        self.assertEqual(512, samples[0].resource_metadata['memory_mb'])
        self.assertEqual(20, samples[0].resource_metadata['disk_gb'])
        self.assertEqual(20, samples[0].resource_metadata['root_gb'])
        self.assertEqual(0, samples[0].resource_metadata['ephemeral_gb'])
        self.assertEqual('active', samples[0].resource_metadata['status'])
        self.assertEqual('active', samples[0].resource_metadata['state'])
        self.assertIsNone(samples[0].resource_metadata['task_state'])

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_reserved_metadata_with_keys(self):
        self.CONF.set_override('reserved_metadata_keys', ['fqdn'])

        mgr = manager.AgentManager(0, self.CONF)
        pollster = instance_stats.CPUPollster(self.CONF)
        samples = list(pollster.get_samples(mgr, {}, [self.instance]))
        self.assertEqual({'fqdn': 'vm_fqdn',
                          'stack': '2cadc4b4-8789-123c-b4eg-edd2f0a9c128'},
                         samples[0].resource_metadata['user_metadata'])

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_reserved_metadata_with_namespace(self):
        mgr = manager.AgentManager(0, self.CONF)
        pollster = instance_stats.CPUPollster(self.CONF)
        samples = list(pollster.get_samples(mgr, {}, [self.instance]))
        self.assertEqual({'stack': '2cadc4b4-8789-123c-b4eg-edd2f0a9c128'},
                         samples[0].resource_metadata['user_metadata'])

        self.CONF.set_override('reserved_metadata_namespace', [])
        mgr = manager.AgentManager(0, self.CONF)
        pollster = instance_stats.CPUPollster(self.CONF)
        samples = list(pollster.get_samples(mgr, {}, [self.instance]))
        self.assertNotIn('user_metadata', samples[0].resource_metadata)

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_flavor_name_as_metadata_instance_type(self):
        mgr = manager.AgentManager(0, self.CONF)
        pollster = instance_stats.CPUPollster(self.CONF)
        samples = list(pollster.get_samples(mgr, {}, [self.instance]))
        self.assertEqual(1, len(samples))
        self.assertEqual('m1.small',
                         samples[0].resource_metadata['instance_type'])


class TestCPUUtilPollster(base.TestPollsterBase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_samples(self):
        self._mock_inspect_instance(
            virt_inspector.InstanceStats(cpu_util=40),
            virt_inspector.InstanceStats(cpu_util=60),
        )

        mgr = manager.AgentManager(0, self.CONF)
        pollster = instance_stats.CPUUtilPollster(self.CONF)

        def _verify_cpu_util_metering(expected_util):
            cache = {}
            samples = list(pollster.get_samples(mgr, cache, [self.instance]))
            self.assertEqual(1, len(samples))
            self.assertEqual(set(['cpu_util']),
                             set([s.name for s in samples]))
            self.assertEqual(expected_util, samples[0].volume)

        _verify_cpu_util_metering(40)
        _verify_cpu_util_metering(60)


class TestCPUL3CachePollster(base.TestPollsterBase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_samples(self):
        self._mock_inspect_instance(
            virt_inspector.InstanceStats(cpu_l3_cache_usage=90112),
            virt_inspector.InstanceStats(cpu_l3_cache_usage=180224),
        )

        mgr = manager.AgentManager(0, self.CONF)
        pollster = instance_stats.CPUL3CachePollster(self.CONF)

        def _verify_cpu_l3_cache_metering(expected_usage):
            cache = {}
            samples = list(pollster.get_samples(mgr, cache, [self.instance]))
            self.assertEqual(1, len(samples))
            self.assertEqual(set(['cpu_l3_cache']),
                             set([s.name for s in samples]))
            self.assertEqual(expected_usage, samples[0].volume)

        _verify_cpu_l3_cache_metering(90112)
        _verify_cpu_l3_cache_metering(180224)
