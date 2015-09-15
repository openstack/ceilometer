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

import mock
from oslo_config import fixture as fixture_config

from ceilometer.agent import manager
from ceilometer.compute.pollsters import instance as pollsters_instance
from ceilometer.tests.unit.compute.pollsters import base


class TestInstancePollster(base.TestPollsterBase):

    def setUp(self):
        super(TestInstancePollster, self).setUp()

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_samples_instance(self):
        mgr = manager.AgentManager()
        pollster = pollsters_instance.InstancePollster()
        samples = list(pollster.get_samples(mgr, {}, [self.instance]))
        self.assertEqual(1, len(samples))
        self.assertEqual('instance', samples[0].name)
        self.assertEqual(1, samples[0].resource_metadata['vcpus'])
        self.assertEqual(512, samples[0].resource_metadata['memory_mb'])
        self.assertEqual(20, samples[0].resource_metadata['disk_gb'])
        self.assertEqual(20, samples[0].resource_metadata['root_gb'])
        self.assertEqual(0, samples[0].resource_metadata['ephemeral_gb'])
        self.assertEqual('active', samples[0].resource_metadata['status'])
        self.assertEqual('active', samples[0].resource_metadata['state'])

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_reserved_metadata_with_keys(self):
        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.CONF.set_override('reserved_metadata_keys', ['fqdn'])

        mgr = manager.AgentManager()
        pollster = pollsters_instance.InstancePollster()
        samples = list(pollster.get_samples(mgr, {}, [self.instance]))
        self.assertEqual({'fqdn': 'vm_fqdn',
                          'stack': '2cadc4b4-8789-123c-b4eg-edd2f0a9c128'},
                         samples[0].resource_metadata['user_metadata'])

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_reserved_metadata_with_namespace(self):
        mgr = manager.AgentManager()
        pollster = pollsters_instance.InstancePollster()
        samples = list(pollster.get_samples(mgr, {}, [self.instance]))
        self.assertEqual({'stack': '2cadc4b4-8789-123c-b4eg-edd2f0a9c128'},
                         samples[0].resource_metadata['user_metadata'])

        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.CONF.set_override('reserved_metadata_namespace', [])
        mgr = manager.AgentManager()
        pollster = pollsters_instance.InstancePollster()
        samples = list(pollster.get_samples(mgr, {}, [self.instance]))
        self.assertNotIn('user_metadata', samples[0].resource_metadata)

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_get_flavor_name_as_metadata_instance_type(self):
        mgr = manager.AgentManager()
        pollster = pollsters_instance.InstancePollster()
        samples = list(pollster.get_samples(mgr, {}, [self.instance]))
        self.assertEqual(1, len(samples))
        self.assertEqual('m1.small',
                         samples[0].resource_metadata['instance_type'])
