# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
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

from ceilometer.compute import manager
from ceilometer import nova_client
from ceilometer.openstack.common.fixture import mockpatch
from ceilometer.openstack.common import test
from ceilometer.tests import agentbase


class TestManager(test.BaseTestCase):

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
        super(TestRunTasks, self).setUp()

        # Set up a fake instance value to be returned by
        # instance_get_all_by_host() so when the manager gets the list
        # of instances to poll we can control the results.
        self.instance = self._fake_instance('faux', 'active')
        stillborn_instance = self._fake_instance('stillborn', 'error')

        def instance_get_all_by_host(*args):
            return [self.instance, stillborn_instance]

        self.useFixture(mockpatch.PatchObject(
            nova_client.Client,
            'instance_get_all_by_host',
            side_effect=lambda *x: [self.instance, stillborn_instance]))

    def test_setup_polling_tasks(self):
        super(TestRunTasks, self).test_setup_polling_tasks()
        self.assertTrue(self.Pollster.samples[0][1] is self.instance)

    def test_interval_exception_isolation(self):
        super(TestRunTasks, self).test_interval_exception_isolation()
        self.assertEqual(len(self.PollsterException.samples), 1)
        self.assertEqual(len(self.PollsterExceptionAnother.samples), 1)

    def test_manager_exception_persistency(self):
        super(TestRunTasks, self).test_manager_exception_persistency()
        with mock.patch.object(nova_client.Client, 'instance_get_all_by_host',
                               side_effect=lambda *x: self._raise_exception()):
            mgr = manager.AgentManager()
            polling_task = manager.PollingTask(mgr)
            polling_task.poll_and_publish()
