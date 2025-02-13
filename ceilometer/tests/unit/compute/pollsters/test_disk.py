# Copyright 2025 Catalyst Cloud Limited
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

from unittest import mock

from ceilometer.compute.pollsters import disk
from ceilometer.polling import manager
from ceilometer.tests.unit.compute.pollsters import base


class TestDiskPollsterBase(base.TestPollsterBase):

    TYPE = 'gauge'

    def setUp(self):
        super().setUp()
        self.instances = self._get_fake_instances()

    def _get_fake_instances(self, ephemeral=0):
        instances = []
        for i in [1, 2]:
            instance = mock.MagicMock()
            instance.name = f'instance-{i}'
            setattr(instance, 'OS-EXT-SRV-ATTR:instance_name',
                    instance.name)
            instance.id = i
            instance.flavor = {'name': 'm1.small', 'id': 2, 'vcpus': 1,
                               'ram': 512, 'disk': 20, 'ephemeral': ephemeral}
            instance.status = 'active'
            instances.append(instance)
        return instances

    def _check_get_samples(self,
                           factory,
                           name,
                           instances=None,
                           expected_count=2):
        pollster = factory(self.CONF)
        mgr = manager.AgentManager(0, self.CONF)
        samples = list(pollster.get_samples(mgr,
                                            {},
                                            instances or self.instances))
        self.assertGreater(len(samples), 0)
        self.assertEqual({name}, set(s.name for s in samples),
                         (f"Only samples for meter {name} "
                          "should be published"))
        self.assertEqual(expected_count, len(samples))
        return samples


class TestDiskSizePollsters(TestDiskPollsterBase):

    TYPE = 'gauge'

    def test_ephemeral_disk_zero(self):
        samples = {
            sample.resource_id: sample
            for sample in self._check_get_samples(
                disk.EphemeralSizePollster,
                'disk.ephemeral.size',
                expected_count=len(self.instances))}
        for instance in self.instances:
            with self.subTest(instance.name):
                self.assertIn(instance.id, samples)
                sample = samples[instance.id]
                self.assertEqual(instance.flavor['ephemeral'],
                                 sample.volume)
                self.assertEqual(self.TYPE, sample.type)

    def test_ephemeral_disk_nonzero(self):
        instances = self._get_fake_instances(ephemeral=10)
        samples = {
            sample.resource_id: sample
            for sample in self._check_get_samples(
                disk.EphemeralSizePollster,
                'disk.ephemeral.size',
                instances=instances,
                expected_count=len(instances))}
        for instance in instances:
            with self.subTest(instance.name):
                self.assertIn(instance.id, samples)
                sample = samples[instance.id]
                self.assertEqual(instance.flavor['ephemeral'],
                                 sample.volume)
                self.assertEqual(self.TYPE, sample.type)

    def test_root_disk(self):
        samples = {
            sample.resource_id: sample
            for sample in self._check_get_samples(
                disk.RootSizePollster,
                'disk.root.size',
                expected_count=len(self.instances))}
        for instance in self.instances:
            with self.subTest(instance.name):
                self.assertIn(instance.id, samples)
                sample = samples[instance.id]
                self.assertEqual((instance.flavor['disk']
                                  - instance.flavor['ephemeral']),
                                 sample.volume)
                self.assertEqual(self.TYPE, sample.type)

    def test_root_disk_ephemeral_nonzero(self):
        instances = self._get_fake_instances(ephemeral=10)
        samples = {
            sample.resource_id: sample
            for sample in self._check_get_samples(
                disk.RootSizePollster,
                'disk.root.size',
                instances=instances,
                expected_count=len(instances))}
        for instance in instances:
            with self.subTest(instance.name):
                self.assertIn(instance.id, samples)
                sample = samples[instance.id]
                self.assertEqual((instance.flavor['disk']
                                  - instance.flavor['ephemeral']),
                                 sample.volume)
                self.assertEqual(self.TYPE, sample.type)
