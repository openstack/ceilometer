#
# Copyright 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
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
"""Tests for ceilometer/agent/manager.py
"""
import mock
from oslotest import base
from oslotest import mockpatch

from ceilometer import agent
from ceilometer.compute import manager
from ceilometer import nova_client
from ceilometer.tests import agentbase


class TestManager(base.BaseTestCase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_load_plugins(self):
        mgr = manager.AgentManager()
        self.assertIsNotNone(list(mgr.pollster_manager))


class TestRunTasks(agentbase.BaseAgentManagerTestCase):

    def _fake_instance(self, name, state):
        instance = mock.MagicMock()
        instance.name = name
        setattr(instance, 'OS-EXT-STS:vm_state', state)
        return instance

    def _raise_exception(self):
        raise Exception

    @staticmethod
    def create_manager():
        return manager.AgentManager()

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        self.source_resources = False
        super(TestRunTasks, self).setUp()

        # Set up a fake instance value to be returned by
        # instance_get_all_by_host() so when the manager gets the list
        # of instances to poll we can control the results.
        self.instances = [self._fake_instance('doing', 'active'),
                          self._fake_instance('resting', 'paused')]
        stillborn_instance = self._fake_instance('stillborn', 'error')

        self.useFixture(mockpatch.PatchObject(
            nova_client.Client,
            'instance_get_all_by_host',
            side_effect=lambda *x: self.instances + [stillborn_instance]))

    def test_setup_polling_tasks(self):
        super(TestRunTasks, self).test_setup_polling_tasks()
        self.assertEqual(self.Pollster.samples[0][1], self.instances)

    def test_interval_exception_isolation(self):
        super(TestRunTasks, self).test_interval_exception_isolation()
        self.assertEqual(1, len(self.PollsterException.samples))
        self.assertEqual(1, len(self.PollsterExceptionAnother.samples))

    def test_manager_exception_persistency(self):
        super(TestRunTasks, self).test_manager_exception_persistency()
        with mock.patch.object(nova_client.Client, 'instance_get_all_by_host',
                               side_effect=lambda *x: self._raise_exception()):
            mgr = manager.AgentManager()
            polling_task = agent.PollingTask(mgr)
            polling_task.poll_and_publish()

    def test_local_instances_default_agent_discovery(self):
        self.setup_pipeline()
        self.assertEqual(self.mgr.default_discovery, ['local_instances'])
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(polling_tasks.get(60))
        self._verify_discovery_params([])
        self.assertEqual(set(self.Pollster.resources),
                         set(self.instances))
