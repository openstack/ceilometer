#
# Copyright 2013 Intel Corp.
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

from ceilometer.agent import manager
from ceilometer.agent import plugin_base
from ceilometer import pipeline
from ceilometer.tests.agent import agentbase


class PollingException(Exception):
    pass


class TestManager(base.BaseTestCase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def test_load_plugins(self):
        mgr = manager.AgentManager()
        self.assertIsNotNone(list(mgr.extensions))

    def test_load_plugins_pollster_list(self):
        mgr = manager.AgentManager(pollster_list=['disk.*'])
        # currently we do have 26 disk-related pollsters
        self.assertEqual(26, len(list(mgr.extensions)))

    def test_load_plugins_no_intersection(self):
        # Let's test nothing will be polled if namespace and pollsters
        # list have no intersection.
        mgr = manager.AgentManager(namespaces=['compute'],
                                   pollster_list=['storage.*'])
        self.assertEqual(0, len(list(mgr.extensions)))

    # Test plugin load behavior based on Node Manager pollsters.
    # pollster_list is just a filter, so sensor pollsters under 'ipmi'
    # namespace would be also instanced. Still need mock __init__ for it.
    @mock.patch('ceilometer.ipmi.pollsters.node._Base.__init__',
                mock.Mock(return_value=None))
    @mock.patch('ceilometer.ipmi.pollsters.sensor.SensorPollster.__init__',
                mock.Mock(return_value=None))
    def test_load_normal_plugins(self):
        mgr = manager.AgentManager(namespaces=['ipmi'],
                                   pollster_list=['hardware.ipmi.node.*'])
        # 2 pollsters for Node Manager
        self.assertEqual(2, len(mgr.extensions))

    # Skip loading pollster upon ExtensionLoadError
    @mock.patch('ceilometer.ipmi.pollsters.node._Base.__init__',
                mock.Mock(side_effect=plugin_base.ExtensionLoadError))
    @mock.patch('ceilometer.ipmi.pollsters.sensor.SensorPollster.__init__',
                mock.Mock(return_value=None))
    def test_load_failed_plugins(self):
        mgr = manager.AgentManager(namespaces=['ipmi'],
                                   pollster_list=['hardware.ipmi.node.*'])
        # 0 pollsters
        self.assertEqual(0, len(mgr.extensions))

    # Exceptions other than ExtensionLoadError are propagated
    @mock.patch('ceilometer.ipmi.pollsters.node._Base.__init__',
                mock.Mock(side_effect=PollingException))
    @mock.patch('ceilometer.ipmi.pollsters.sensor.SensorPollster.__init__',
                mock.Mock(return_value=None))
    def test_load_exceptional_plugins(self):
        self.assertRaises(PollingException,
                          manager.AgentManager,
                          ['ipmi'],
                          ['hardware.ipmi.node.*'])


class TestPollsterKeystone(agentbase.TestPollster):
    @plugin_base.check_keystone
    def get_samples(self, manager, cache, resources):
        func = super(TestPollsterKeystone, self).get_samples
        return func(manager=manager,
                    cache=cache,
                    resources=resources)


class TestPollsterPollingException(agentbase.TestPollster):
    polling_failures = 0

    def get_samples(self, manager, cache, resources):
        func = super(TestPollsterPollingException, self).get_samples
        sample = func(manager=manager,
                      cache=cache,
                      resources=resources)

        # Raise polling exception after 2 times
        self.polling_failures += 1
        if self.polling_failures > 2:
            raise plugin_base.PollsterPermanentError()

        return sample


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

    class PollsterPollingException(TestPollsterPollingException):
        samples = []
        resources = []
        test_data = agentbase.TestSample(
            name='testpollingexception',
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
        self.PollsterPollingException.samples = []
        self.PollsterPollingException.resources = []
        super(TestRunTasks, self).tearDown()

    def create_extension_list(self):
        exts = super(TestRunTasks, self).create_extension_list()
        exts.extend([extension.Extension('testkeystone',
                                         None,
                                         None,
                                         self.PollsterKeystone(), ),
                     extension.Extension('testpollingexception',
                                         None,
                                         None,
                                         self.PollsterPollingException(), )])
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

    def test_interval_exception_isolation(self):
        super(TestRunTasks, self).test_interval_exception_isolation()
        self.assertEqual(1, len(self.PollsterException.samples))
        self.assertEqual(1, len(self.PollsterExceptionAnother.samples))

    def test_polling_exception(self):
        self.pipeline_cfg = [
            {
                'name': "test_pollingexception",
                'interval': 10,
                'counters': ['testpollingexception'],
                'resources': ['test://'] if self.source_resources else [],
                'transformers': [],
                'publishers': ["test"],
            },
        ]
        self.mgr.pipeline_manager = pipeline.PipelineManager(
            self.pipeline_cfg,
            self.transformer_manager)
        polling_tasks = self.mgr.setup_polling_tasks()

        # 2 samples after 4 pollings, as pollster got disabled unpon exception
        for x in range(0, 4):
            self.mgr.interval_task(polling_tasks.values()[0])
        pub = self.mgr.pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(2, len(pub.samples))
