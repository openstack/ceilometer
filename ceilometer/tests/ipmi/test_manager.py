# Copyright 2014 Intel Corp.
#
# Author: Zhai Edwin <edwin.zhai@intel.com>
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
"""Tests for ceilometer/ipmi/manager.py
"""

from ceilometer.ipmi import manager
from ceilometer.tests import agentbase

import mock
from oslotest import base


class TestManager(base.BaseTestCase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_load_plugins(self):
        mgr = manager.AgentManager()
        self.assertIsNotNone(list(mgr.pollster_manager))


class TestRunTasks(agentbase.BaseAgentManagerTestCase):

    @staticmethod
    def create_manager():
        return manager.AgentManager()

    def setUp(self):
        self.source_resources = True
        super(TestRunTasks, self).setUp()
