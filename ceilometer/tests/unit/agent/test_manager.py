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
"""Tests for ceilometer agent manager"""

import shutil

from keystoneclient import exceptions as ks_exceptions
import mock
from novaclient import client as novaclient
from oslo_config import fixture as fixture_config
from oslo_service import service as os_service
from oslo_utils import fileutils
from oslotest import base
from oslotest import mockpatch
import requests
import six
from stevedore import extension
import yaml

from ceilometer.agent import manager
from ceilometer.agent import plugin_base
from ceilometer.hardware import discovery
from ceilometer import pipeline
from ceilometer.tests.unit.agent import agentbase


class PollingException(Exception):
    pass


class TestPollsterBuilder(agentbase.TestPollster):
    @classmethod
    def build_pollsters(cls):
        return [('builder1', cls()), ('builder2', cls())]


@mock.patch('ceilometer.compute.pollsters.'
            'BaseComputePollster.setup_environment',
            mock.Mock(return_value=None))
class TestManager(base.BaseTestCase):
    def setUp(self):
        super(TestManager, self).setUp()
        self.conf = self.useFixture(fixture_config.Config()).conf
        self.conf(args=[])

    @mock.patch('ceilometer.pipeline.setup_polling', mock.MagicMock())
    def test_load_plugins(self):
        mgr = manager.AgentManager()
        self.assertIsNotNone(list(mgr.extensions))

    def test_load_plugins_pollster_list(self):
        mgr = manager.AgentManager(pollster_list=['disk.*'])
        # currently we do have 26 disk-related pollsters
        self.assertEqual(26, len(list(mgr.extensions)))

    def test_load_invalid_plugins_pollster_list(self):
        # if no valid pollsters have been loaded, the ceilometer
        # polling program should exit
        self.assertRaisesRegexp(
            manager.EmptyPollstersList,
            'No valid pollsters can be loaded with the startup parameters'
            ' polling-namespaces and pollster-list.',
            manager.AgentManager,
            pollster_list=['aaa'])

    def test_load_plugins_no_intersection(self):
        # Let's test nothing will be polled if namespace and pollsters
        # list have no intersection.
        parameters = dict(namespaces=['compute'],
                          pollster_list=['storage.*'])
        self.assertRaisesRegexp(
            manager.EmptyPollstersList,
            'No valid pollsters can be loaded with the startup parameters'
            ' polling-namespaces and pollster-list.',
            manager.AgentManager,
            parameters)

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
        # 8 pollsters for Node Manager
        self.assertEqual(8, len(mgr.extensions))

    # Skip loading pollster upon ExtensionLoadError
    @mock.patch('ceilometer.ipmi.pollsters.node._Base.__init__',
                mock.Mock(side_effect=plugin_base.ExtensionLoadError))
    @mock.patch('ceilometer.ipmi.pollsters.sensor.SensorPollster.__init__',
                mock.Mock(return_value=None))
    @mock.patch('ceilometer.agent.manager.LOG')
    def test_load_failed_plugins(self, LOG):
        # Here we additionally check that namespaces will be converted to the
        # list if param was not set as a list.
        try:
            manager.AgentManager(namespaces='ipmi',
                                 pollster_list=['hardware.ipmi.node.*'])
        except manager.EmptyPollstersList:
            err_msg = 'Skip loading extension for hardware.ipmi.node.%s'
            pollster_names = [
                'power', 'temperature', 'outlet_temperature',
                'airflow', 'cups', 'cpu_util', 'mem_util', 'io_util']
            calls = [mock.call(err_msg % n) for n in pollster_names]
            LOG.exception.assert_has_calls(calls=calls, any_order=True)

    # Skip loading pollster upon ImportError
    @mock.patch('ceilometer.ipmi.pollsters.node._Base.__init__',
                mock.Mock(side_effect=ImportError))
    @mock.patch('ceilometer.ipmi.pollsters.sensor.SensorPollster.__init__',
                mock.Mock(return_value=None))
    def test_import_error_in_plugin(self):
        parameters = dict(namespaces=['ipmi'],
                          pollster_list=['hardware.ipmi.node.*'])
        self.assertRaisesRegexp(
            manager.EmptyPollstersList,
            'No valid pollsters can be loaded with the startup parameters'
            ' polling-namespaces and pollster-list.',
            manager.AgentManager,
            parameters)

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

    def test_load_plugins_pollster_list_forbidden(self):
        manager.cfg.CONF.set_override('backend_url', 'http://',
                                      group='coordination')
        self.assertRaises(manager.PollsterListForbidden,
                          manager.AgentManager,
                          pollster_list=['disk.*'])
        manager.cfg.CONF.reset()

    def test_builder(self):
        @staticmethod
        def fake_get_ext_mgr(namespace):
            if 'builder' in namespace:
                return extension.ExtensionManager.make_test_instance(
                    [
                        extension.Extension('builder',
                                            None,
                                            TestPollsterBuilder,
                                            None),
                    ]
                )
            else:
                return extension.ExtensionManager.make_test_instance(
                    [
                        extension.Extension('test',
                                            None,
                                            None,
                                            agentbase.TestPollster()),
                    ]
                )

        with mock.patch.object(manager.AgentManager, '_get_ext_mgr',
                               new=fake_get_ext_mgr):
            mgr = manager.AgentManager(namespaces=['central'])
            self.assertEqual(3, len(mgr.extensions))
            for ext in mgr.extensions:
                self.assertIn(ext.name, ['builder1', 'builder2', 'test'])
                self.assertIsInstance(ext.obj, agentbase.TestPollster)


class TestPollsterKeystone(agentbase.TestPollster):
    def get_samples(self, manager, cache, resources):
        # Just try to use keystone, that will raise an exception
        manager.keystone.projects.list()


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
            raise plugin_base.PollsterPermanentError(resources)

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
    @mock.patch('ceilometer.compute.pollsters.'
                'BaseComputePollster.setup_environment',
                mock.Mock(return_value=None))
    def create_manager():
        return manager.AgentManager()

    @staticmethod
    def setup_pipeline_file(pipeline):
        if six.PY3:
            pipeline = pipeline.encode('utf-8')

        pipeline_cfg_file = fileutils.write_to_tempfile(content=pipeline,
                                                        prefix="pipeline",
                                                        suffix="yaml")
        return pipeline_cfg_file

    def fake_notifier_sample(self, ctxt, event_type, payload):
        for m in payload['samples']:
            del m['message_signature']
            self.notified_samples.append(m)

    def setUp(self):
        self.notified_samples = []
        self.notifier = mock.Mock()
        self.notifier.sample.side_effect = self.fake_notifier_sample
        self.useFixture(mockpatch.Patch('oslo_messaging.Notifier',
                                        return_value=self.notifier))
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
        self.mgr.interval_task(list(polling_tasks.values())[0])
        self.assertTrue(self.Pollster.resources)

    def test_when_keystone_fail(self):
        """Test for bug 1316532."""
        self.useFixture(mockpatch.Patch(
            'keystoneclient.v2_0.client.Client',
            side_effect=ks_exceptions.ClientException))
        self.pipeline_cfg = {
            'sources': [{
                'name': "test_keystone",
                'interval': 10,
                'meters': ['testkeystone'],
                'resources': ['test://'] if self.source_resources else [],
                'sinks': ['test_sink']}],
            'sinks': [{
                'name': 'test_sink',
                'transformers': [],
                'publishers': ["test"]}]
        }
        self.mgr.polling_manager = pipeline.PollingManager(self.pipeline_cfg)
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(list(polling_tasks.values())[0])
        self.assertFalse(self.PollsterKeystone.samples)
        self.assertFalse(self.notified_samples)

    @mock.patch('ceilometer.agent.manager.LOG')
    @mock.patch('ceilometer.nova_client.LOG')
    def test_hardware_discover_fail_minimize_logs(self, novalog, baselog):
        self.useFixture(mockpatch.PatchObject(
            novaclient.HTTPClient,
            'authenticate',
            side_effect=requests.ConnectionError))

        class PollsterHardware(agentbase.TestPollster):
            discovery = 'tripleo_overcloud_nodes'

        class PollsterHardwareAnother(agentbase.TestPollster):
            discovery = 'tripleo_overcloud_nodes'

        self.mgr.extensions.extend([
            extension.Extension('testhardware',
                                None,
                                None,
                                PollsterHardware(), ),
            extension.Extension('testhardware2',
                                None,
                                None,
                                PollsterHardwareAnother(), )
        ])
        ext = extension.Extension('tripleo_overcloud_nodes',
                                  None,
                                  None,
                                  discovery.NodesDiscoveryTripleO())
        self.mgr.discovery_manager = (extension.ExtensionManager
                                      .make_test_instance([ext]))

        self.pipeline_cfg = {
            'sources': [{
                'name': "test_hardware",
                'interval': 10,
                'meters': ['testhardware', 'testhardware2'],
                'sinks': ['test_sink']}],
            'sinks': [{
                'name': 'test_sink',
                'transformers': [],
                'publishers': ["test"]}]
        }
        self.mgr.polling_manager = pipeline.PollingManager(self.pipeline_cfg)
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(list(polling_tasks.values())[0])
        self.assertEqual(1, novalog.exception.call_count)
        self.assertFalse(baselog.exception.called)

    @mock.patch('ceilometer.agent.manager.LOG')
    def test_polling_exception(self, LOG):
        source_name = 'test_pollingexception'
        self.pipeline_cfg = {
            'sources': [{
                'name': source_name,
                'interval': 10,
                'meters': ['testpollingexception'],
                'resources': ['test://'] if self.source_resources else [],
                'sinks': ['test_sink']}],
            'sinks': [{
                'name': 'test_sink',
                'transformers': [],
                'publishers': ["test"]}]
        }
        self.mgr.polling_manager = pipeline.PollingManager(self.pipeline_cfg)
        polling_task = list(self.mgr.setup_polling_tasks().values())[0]
        pollster = list(polling_task.pollster_matches[source_name])[0]

        # 2 samples after 4 pollings, as pollster got disabled upon exception
        for x in range(0, 4):
            self.mgr.interval_task(polling_task)
        samples = self.notified_samples
        self.assertEqual(2, len(samples))
        LOG.error.assert_called_once_with((
            'Prevent pollster %(name)s for '
            'polling source %(source)s anymore!')
            % ({'name': pollster.name, 'source': source_name}))

    def test_batching_polled_samples_false(self):
        self.CONF.set_override('batch_polled_samples', False)
        self._batching_samples(4, 4)

    def test_batching_polled_samples_true(self):
        self.CONF.set_override('batch_polled_samples', True)
        self._batching_samples(4, 1)

    def test_batching_polled_samples_default(self):
        self._batching_samples(4, 1)

    def _batching_samples(self, expected_samples, call_count):
        pipeline = yaml.dump({
            'sources': [{
                'name': 'test_pipeline',
                'interval': 1,
                'meters': ['testbatch'],
                'resources': ['alpha', 'beta', 'gamma', 'delta'],
                'sinks': ['test_sink']}],
            'sinks': [{
                'name': 'test_sink',
                'transformers': [],
                'publishers': ["test"]}]
        })

        pipeline_cfg_file = self.setup_pipeline_file(pipeline)

        self.CONF.set_override("pipeline_cfg_file", pipeline_cfg_file)

        self.mgr.tg = os_service.threadgroup.ThreadGroup(1000)
        self.mgr.start()
        # Manually executes callbacks
        for timer in self.mgr.pollster_timers:
            timer.f(*timer.args, **timer.kw)

        samples = self.notified_samples
        self.assertEqual(expected_samples, len(samples))
        self.assertEqual(call_count, self.notifier.sample.call_count)

    def test_start_with_reloadable_pipeline(self):

        self.CONF.set_override('heartbeat', 1.0, group='coordination')
        self.CONF.set_override('refresh_pipeline_cfg', True)
        self.CONF.set_override('pipeline_polling_interval', 2)

        pipeline = yaml.dump({
            'sources': [{
                'name': 'test_pipeline',
                'interval': 1,
                'meters': ['test'],
                'resources': ['test://'] if self.source_resources else [],
                'sinks': ['test_sink']}],
            'sinks': [{
                'name': 'test_sink',
                'transformers': [],
                'publishers': ["test"]}]
        })

        pipeline_cfg_file = self.setup_pipeline_file(pipeline)

        self.CONF.set_override("pipeline_cfg_file", pipeline_cfg_file)
        self.mgr.tg = os_service.threadgroup.ThreadGroup(1000)
        self.mgr.start()

        # we only got the old name of meters
        for sample in self.notified_samples:
            self.assertEqual('test', sample['counter_name'])
            self.assertEqual(1, sample['counter_volume'])
            self.assertEqual('test_run_tasks', sample['resource_id'])

        # Modify the collection targets
        pipeline = yaml.dump({
            'sources': [{
                'name': 'test_pipeline',
                'interval': 1,
                'meters': ['testanother'],
                'resources': ['test://'] if self.source_resources else [],
                'sinks': ['test_sink']}],
            'sinks': [{
                'name': 'test_sink',
                'transformers': [],
                'publishers': ["test"]}]
        })

        updated_pipeline_cfg_file = self.setup_pipeline_file(pipeline)

        # Move/re-name the updated pipeline file to the original pipeline
        # file path as recorded in oslo config
        shutil.move(updated_pipeline_cfg_file, pipeline_cfg_file)

        # Flush notified samples to test only new, nothing latent on
        # fake message bus.
        self.notified_samples = []

        # we only got the new name of meters
        for sample in self.notified_samples:
            self.assertEqual('testanother', sample['counter_name'])
            self.assertEqual(1, sample['counter_volume'])
            self.assertEqual('test_run_tasks', sample['resource_id'])
