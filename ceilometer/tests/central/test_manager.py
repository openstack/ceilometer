#
# Copyright 2013 Intel Corp.
#
# Author: Lianhao Lu <lianhao.lu@intel.com>
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
"""Tests for ceilometer/central/manager.py
"""

import mock
from oslotest import base
from oslotest import mockpatch
from stevedore import extension

from ceilometer.central import manager
from ceilometer.central import plugin
from ceilometer import pipeline
from ceilometer.tests import agentbase


class TestManager(base.BaseTestCase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_load_plugins(self):
        mgr = manager.AgentManager()
        self.assertIsNotNone(list(mgr.pollster_manager))


class TestPollsterKeystone(agentbase.TestPollster):
    @plugin.check_keystone
    def get_samples(self, manager, cache, resources=None):
        func = super(TestPollsterKeystone, self).get_samples
        return func(manager=manager,
                    cache=cache,
                    resources=resources)


class TestRunTasks(agentbase.BaseAgentManagerTestCase):

    class PollsterKeystone(TestPollsterKeystone):
        samples = []
        resources = []
        test_data = agentbase.TestSample(
            name='testkeystone',
            type=agentbase.default_test_data.type,
            unit=agentbase.default_test_data.unit,
            volume=agentbase.default_test_data.volume,
            user_id=agentbase.default_test_data.user_id,
            project_id=agentbase.default_test_data.project_id,
            resource_id=agentbase.default_test_data.resource_id,
            timestamp=agentbase.default_test_data.timestamp,
            resource_metadata=agentbase.default_test_data.resource_metadata)

    @staticmethod
    def create_manager():
        return manager.AgentManager()

    def setUp(self):
        self.source_resources = True
        super(TestRunTasks, self).setUp()
        self.useFixture(mockpatch.Patch(
            'keystoneclient.v2_0.client.Client',
            return_value=mock.Mock()))

    def tearDown(self):
        self.PollsterKeystone.samples = []
        self.PollsterKeystone.resources = []
        super(TestRunTasks, self).tearDown()

    def get_extension_list(self):
        exts = super(TestRunTasks, self).get_extension_list()
        exts.append(extension.Extension('testkeystone',
                                        None,
                                        None,
                                        self.PollsterKeystone(),))
        return exts

    def test_get_sample_resources(self):
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(polling_tasks.values()[0])
        self.assertTrue(self.Pollster.resources)

    def test_when_keystone_fail(self):
        """Test for bug 1316532."""
        self.useFixture(mockpatch.Patch(
            'keystoneclient.v2_0.client.Client',
            side_effect=Exception))
        self.pipeline_cfg = [
            {
                'name': "test_keystone",
                'interval': 10,
                'counters': ['testkeystone'],
                'resources': ['test://'] if self.source_resources else [],
                'transformers': [],
                'publishers': ["test"],
            },
        ]
        self.mgr.pipeline_manager = pipeline.PipelineManager(
            self.pipeline_cfg,
            self.transformer_manager)
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(polling_tasks.values()[0])
        self.assertFalse(self.PollsterKeystone.samples)
