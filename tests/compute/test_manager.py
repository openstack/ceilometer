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

import datetime

import mock
from oslo.config import cfg
from stevedore import extension
from stevedore.tests import manager as extension_tests
from stevedore import dispatch

from ceilometer import nova_client
from ceilometer.compute import manager
from ceilometer import counter
from ceilometer import pipeline
from ceilometer.tests import base

from tests import agentbase


@mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
def test_load_plugins():
    mgr = manager.AgentManager()
    assert list(mgr.pollster_manager), 'Failed to load any plugins'
    return


class TestRunTasks(agentbase.BaseAgentManagerTestCase):

    def _fake_instance(self, name, state):
        instance = mock.MagicMock()
        instance.name = name
        setattr(instance, 'OS-EXT-STS:vm_state', state)
        return instance

    def setup_manager(self):
        self.mgr = manager.AgentManager()

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(TestRunTasks, self).setUp()

        # Set up a fake instance value to be returned by
        # instance_get_all_by_host() so when the manager gets the list
        # of instances to poll we can control the results.
        self.instance = self._fake_instance('faux', 'active')
        stillborn_instance = self._fake_instance('stillborn', 'error')
        self.stubs.Set(nova_client.Client, 'instance_get_all_by_host',
                       lambda *x: [self.instance, stillborn_instance])

    def test_notifier_task(self):
        self.mgr.setup_notifier_task()
        self.mgr.poll_instance(None, self.instance)
        self.assertEqual(len(self.Pollster.counters), 1)
        assert self.publisher.counters[0] == self.Pollster.test_data

    def test_setup_polling_tasks(self):
        super(TestRunTasks, self).test_setup_polling_tasks()
        self.assertTrue(self.Pollster.counters[0][1] is self.instance)

    def test_interval_exception_isolation(self):
        super(TestRunTasks, self).test_interval_exception_isolation()
        self.assertEqual(len(self.PollsterException.counters), 1)
        self.assertEqual(len(self.PollsterExceptionAnother.counters), 1)
