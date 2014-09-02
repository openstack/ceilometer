#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 Intel corp.
# Copyright 2013 eNovance
# Copyright 2014 Red Hat, Inc
#
# Authors: Yunhong Jiang <yunhong.jiang@intel.com>
#          Julien Danjou <julien@danjou.info>
#          Eoghan Glynn <eglynn@redhat.com>
#          Nejc Saje <nsaje@redhat.com>
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

import abc
import copy
import datetime

import mock
from oslo.config import fixture as fixture_config
from oslotest import mockpatch
import six
from stevedore import extension

from ceilometer import pipeline
from ceilometer import plugin
from ceilometer import publisher
from ceilometer.publisher import test as test_publisher
from ceilometer import sample
from ceilometer.tests import base
from ceilometer import transformer


class TestSample(sample.Sample):
    def __init__(self, name, type, unit, volume, user_id, project_id,
                 resource_id, timestamp, resource_metadata, source=None):
        super(TestSample, self).__init__(name, type, unit, volume, user_id,
                                         project_id, resource_id, timestamp,
                                         resource_metadata, source)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        return False

    def __ne__(self, other):
        return not self.__eq__(other)


default_test_data = TestSample(
    name='test',
    type=sample.TYPE_CUMULATIVE,
    unit='',
    volume=1,
    user_id='test',
    project_id='test',
    resource_id='test_run_tasks',
    timestamp=datetime.datetime.utcnow().isoformat(),
    resource_metadata={'name': 'Pollster'},
)


class TestPollster(plugin.PollsterBase):
    test_data = default_test_data

    def get_samples(self, manager, cache, resources=None):
        resources = resources or []
        self.samples.append((manager, resources))
        self.resources.extend(resources)
        c = copy.copy(self.test_data)
        c.resource_metadata['resources'] = resources
        return [c]


class TestPollsterException(TestPollster):
    def get_samples(self, manager, cache, resources=None):
        resources = resources or []
        self.samples.append((manager, resources))
        self.resources.extend(resources)
        raise Exception()


class TestDiscovery(plugin.DiscoveryBase):
    def discover(self, param=None):
        self.params.append(param)
        return self.resources


class TestDiscoveryException(plugin.DiscoveryBase):
    def discover(self, param=None):
        self.params.append(param)
        raise Exception()


@six.add_metaclass(abc.ABCMeta)
class BaseAgentManagerTestCase(base.BaseTestCase):

    class Pollster(TestPollster):
        samples = []
        resources = []
        test_data = default_test_data

    class PollsterAnother(TestPollster):
        samples = []
        resources = []
        test_data = TestSample(
            name='testanother',
            type=default_test_data.type,
            unit=default_test_data.unit,
            volume=default_test_data.volume,
            user_id=default_test_data.user_id,
            project_id=default_test_data.project_id,
            resource_id=default_test_data.resource_id,
            timestamp=default_test_data.timestamp,
            resource_metadata=default_test_data.resource_metadata)

    class PollsterException(TestPollsterException):
        samples = []
        resources = []
        test_data = TestSample(
            name='testexception',
            type=default_test_data.type,
            unit=default_test_data.unit,
            volume=default_test_data.volume,
            user_id=default_test_data.user_id,
            project_id=default_test_data.project_id,
            resource_id=default_test_data.resource_id,
            timestamp=default_test_data.timestamp,
            resource_metadata=default_test_data.resource_metadata)

    class PollsterExceptionAnother(TestPollsterException):
        samples = []
        resources = []
        test_data = TestSample(
            name='testexceptionanother',
            type=default_test_data.type,
            unit=default_test_data.unit,
            volume=default_test_data.volume,
            user_id=default_test_data.user_id,
            project_id=default_test_data.project_id,
            resource_id=default_test_data.resource_id,
            timestamp=default_test_data.timestamp,
            resource_metadata=default_test_data.resource_metadata)

    class Discovery(TestDiscovery):
        params = []
        resources = []

    class DiscoveryAnother(TestDiscovery):
        params = []
        resources = []

        @property
        def group_id(self):
            return 'another_group'

    class DiscoveryException(TestDiscoveryException):
        params = []

    def setup_pipeline(self):
        self.transformer_manager = transformer.TransformerExtensionManager(
            'ceilometer.transformer',
        )
        self.mgr.pipeline_manager = pipeline.PipelineManager(
            self.pipeline_cfg,
            self.transformer_manager)

    def get_extension_list(self):
        return [extension.Extension('test',
                                    None,
                                    None,
                                    self.Pollster(), ),
                extension.Extension('testanother',
                                    None,
                                    None,
                                    self.PollsterAnother(), ),
                extension.Extension('testexception',
                                    None,
                                    None,
                                    self.PollsterException(), ),
                extension.Extension('testexceptionanother',
                                    None,
                                    None,
                                    self.PollsterExceptionAnother(), )]

    def create_pollster_manager(self):
        return extension.ExtensionManager.make_test_instance(
            self.get_extension_list(),
        )

    def create_discovery_manager(self):
        return extension.ExtensionManager.make_test_instance(
            [
                extension.Extension(
                    'testdiscovery',
                    None,
                    None,
                    self.Discovery(), ),
                extension.Extension(
                    'testdiscoveryanother',
                    None,
                    None,
                    self.DiscoveryAnother(), ),
                extension.Extension(
                    'testdiscoveryexception',
                    None,
                    None,
                    self.DiscoveryException(), ),
            ],
        )

    @abc.abstractmethod
    def create_manager(self):
        """Return subclass specific manager."""

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(BaseAgentManagerTestCase, self).setUp()
        self.mgr = self.create_manager()
        self.mgr.pollster_manager = self.create_pollster_manager()
        self.mgr.partition_coordinator = mock.MagicMock()
        fake_subset = lambda _, x: x
        p_coord = self.mgr.partition_coordinator
        p_coord.extract_my_subset.side_effect = fake_subset
        self.mgr.tg = mock.MagicMock()
        self.pipeline_cfg = [{
            'name': "test_pipeline",
            'interval': 60,
            'counters': ['test'],
            'resources': ['test://'] if self.source_resources else [],
            'transformers': [],
            'publishers': ["test"],
        }, ]
        self.setup_pipeline()
        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.CONF.set_override(
            'pipeline_cfg_file',
            self.path_get('etc/ceilometer/pipeline.yaml')
        )
        self.useFixture(mockpatch.PatchObject(
            publisher, 'get_publisher', side_effect=self.get_publisher))

    def get_publisher(self, url, namespace=''):
        fake_drivers = {'test://': test_publisher.TestPublisher,
                        'new://': test_publisher.TestPublisher,
                        'rpc://': test_publisher.TestPublisher}
        return fake_drivers[url](url)

    def tearDown(self):
        self.Pollster.samples = []
        self.PollsterAnother.samples = []
        self.PollsterException.samples = []
        self.PollsterExceptionAnother.samples = []
        self.Pollster.resources = []
        self.PollsterAnother.resources = []
        self.PollsterException.resources = []
        self.PollsterExceptionAnother.resources = []
        self.Discovery.params = []
        self.DiscoveryAnother.params = []
        self.DiscoveryException.params = []
        self.Discovery.resources = []
        self.DiscoveryAnother.resources = []
        super(BaseAgentManagerTestCase, self).tearDown()

    @mock.patch('ceilometer.pipeline.setup_pipeline')
    def test_start(self, setup_pipeline):
        self.mgr.join_partitioning_groups = mock.MagicMock()
        self.mgr.setup_polling_tasks = mock.MagicMock()
        self.CONF.set_override('heartbeat', 1.0, group='coordination')
        self.mgr.start()
        setup_pipeline.assert_called_once_with()
        self.mgr.partition_coordinator.start.assert_called_once_with()
        self.mgr.join_partitioning_groups.assert_called_once_with()
        self.mgr.setup_polling_tasks.assert_called_once_with()
        timer_call = mock.call(1.0, self.mgr.partition_coordinator.heartbeat)
        self.assertEqual([timer_call], self.mgr.tg.add_timer.call_args_list)

    def test_join_partitioning_groups(self):
        self.mgr.discovery_manager = self.create_discovery_manager()
        self.mgr.join_partitioning_groups()
        p_coord = self.mgr.partition_coordinator
        expected = [mock.call(self.mgr._construct_group_id(g))
                    for g in ['another_group', 'global']]
        self.assertEqual(len(expected), len(p_coord.join_group.call_args_list))
        for c in expected:
            self.assertIn(c, p_coord.join_group.call_args_list)

    def test_setup_polling_tasks(self):
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(1, len(polling_tasks))
        self.assertTrue(60 in polling_tasks.keys())
        per_task_resources = polling_tasks[60].resources
        self.assertEqual(1, len(per_task_resources))
        self.assertEqual(set(self.pipeline_cfg[0]['resources']),
                         set(per_task_resources['test'].resources))
        self.mgr.interval_task(polling_tasks.values()[0])
        pub = self.mgr.pipeline_manager.pipelines[0].publishers[0]
        del pub.samples[0].resource_metadata['resources']
        self.assertEqual(self.Pollster.test_data, pub.samples[0])

    def test_setup_polling_tasks_multiple_interval(self):
        self.pipeline_cfg.append({
            'name': "test_pipeline",
            'interval': 10,
            'counters': ['test'],
            'resources': ['test://'] if self.source_resources else [],
            'transformers': [],
            'publishers': ["test"],
        })
        self.setup_pipeline()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(2, len(polling_tasks))
        self.assertTrue(60 in polling_tasks.keys())
        self.assertTrue(10 in polling_tasks.keys())

    def test_setup_polling_tasks_mismatch_counter(self):
        self.pipeline_cfg.append(
            {
                'name': "test_pipeline_1",
                'interval': 10,
                'counters': ['test_invalid'],
                'resources': ['invalid://'],
                'transformers': [],
                'publishers': ["test"],
            })
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(1, len(polling_tasks))
        self.assertTrue(60 in polling_tasks.keys())

    def test_setup_polling_task_same_interval(self):
        self.pipeline_cfg.append({
            'name': "test_pipeline",
            'interval': 60,
            'counters': ['testanother'],
            'resources': ['testanother://'] if self.source_resources else [],
            'transformers': [],
            'publishers': ["test"],
        })
        self.setup_pipeline()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(1, len(polling_tasks))
        pollsters = polling_tasks.get(60).pollsters
        self.assertEqual(2, len(pollsters))
        per_task_resources = polling_tasks[60].resources
        self.assertEqual(2, len(per_task_resources))
        self.assertEqual(set(self.pipeline_cfg[0]['resources']),
                         set(per_task_resources['test'].resources))
        self.assertEqual(set(self.pipeline_cfg[1]['resources']),
                         set(per_task_resources['testanother'].resources))

    def test_interval_exception_isolation(self):
        self.pipeline_cfg = [
            {
                'name': "test_pipeline_1",
                'interval': 10,
                'counters': ['testexceptionanother'],
                'resources': ['test://'] if self.source_resources else [],
                'transformers': [],
                'publishers': ["test"],
            },
            {
                'name': "test_pipeline_2",
                'interval': 10,
                'counters': ['testexception'],
                'resources': ['test://'] if self.source_resources else [],
                'transformers': [],
                'publishers': ["test"],
            },
        ]
        self.mgr.pipeline_manager = pipeline.PipelineManager(
            self.pipeline_cfg,
            self.transformer_manager)

        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(1, len(polling_tasks.keys()))
        polling_tasks.get(10)
        self.mgr.interval_task(polling_tasks.get(10))
        pub = self.mgr.pipeline_manager.pipelines[0].publishers[0]
        self.assertEqual(0, len(pub.samples))

    def test_agent_manager_start(self):
        mgr = self.create_manager()
        mgr.pollster_manager = self.mgr.pollster_manager
        mgr.create_polling_task = mock.MagicMock()
        mgr.tg = mock.MagicMock()
        mgr.start()
        self.assertTrue(mgr.tg.add_timer.called)

    def test_manager_exception_persistency(self):
        self.pipeline_cfg.append({
            'name': "test_pipeline",
            'interval': 60,
            'counters': ['testanother'],
            'transformers': [],
            'publishers': ["test"],
        })
        self.setup_pipeline()

    def _verify_discovery_params(self, expected):
        self.assertEqual(expected, self.Discovery.params)
        self.assertEqual(expected, self.DiscoveryAnother.params)
        self.assertEqual(expected, self.DiscoveryException.params)

    def _do_test_per_agent_discovery(self,
                                     discovered_resources,
                                     static_resources):
        self.mgr.discovery_manager = self.create_discovery_manager()
        if discovered_resources:
            self.mgr.default_discovery = [d.name
                                          for d in self.mgr.discovery_manager]
        self.Discovery.resources = discovered_resources
        self.DiscoveryAnother.resources = [d[::-1]
                                           for d in discovered_resources]
        self.pipeline_cfg[0]['resources'] = static_resources
        self.setup_pipeline()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(polling_tasks.get(60))
        self._verify_discovery_params([None] if discovered_resources else [])
        discovery = self.Discovery.resources + self.DiscoveryAnother.resources
        # compare resource lists modulo ordering
        self.assertEqual(set(static_resources or discovery),
                         set(self.Pollster.resources))

    def test_per_agent_discovery_discovered_only(self):
        self._do_test_per_agent_discovery(['discovered_1', 'discovered_2'],
                                          [])

    def test_per_agent_discovery_static_only(self):
        self._do_test_per_agent_discovery([],
                                          ['static_1', 'static_2'])

    def test_per_agent_discovery_discovered_overridden_by_static(self):
        self._do_test_per_agent_discovery(['discovered_1', 'discovered_2'],
                                          ['static_1', 'static_2'])

    def test_per_agent_discovery_overridden_by_per_pipeline_discovery(self):
        discovered_resources = ['discovered_1', 'discovered_2']
        self.mgr.discovery_manager = self.create_discovery_manager()
        self.Discovery.resources = discovered_resources
        self.DiscoveryAnother.resources = [d[::-1]
                                           for d in discovered_resources]
        self.pipeline_cfg[0]['discovery'] = ['testdiscoveryanother',
                                             'testdiscoverynonexistent',
                                             'testdiscoveryexception']
        self.pipeline_cfg[0]['resources'] = []
        self.setup_pipeline()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(polling_tasks.get(60))
        self.assertEqual(set(self.DiscoveryAnother.resources),
                         set(self.Pollster.resources))

    def _do_test_per_pipeline_discovery(self,
                                        discovered_resources,
                                        static_resources):
        self.mgr.discovery_manager = self.create_discovery_manager()
        self.Discovery.resources = discovered_resources
        self.DiscoveryAnother.resources = [d[::-1]
                                           for d in discovered_resources]
        self.pipeline_cfg[0]['discovery'] = ['testdiscovery',
                                             'testdiscoveryanother',
                                             'testdiscoverynonexistent',
                                             'testdiscoveryexception']
        self.pipeline_cfg[0]['resources'] = static_resources
        self.setup_pipeline()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(polling_tasks.get(60))
        discovery = self.Discovery.resources + self.DiscoveryAnother.resources
        # compare resource lists modulo ordering
        self.assertEqual(set(static_resources + discovery),
                         set(self.Pollster.resources))

    def test_per_pipeline_discovery_discovered_only(self):
        self._do_test_per_pipeline_discovery(['discovered_1', 'discovered_2'],
                                             [])

    def test_per_pipeline_discovery_static_only(self):
        self._do_test_per_pipeline_discovery([],
                                             ['static_1', 'static_2'])

    def test_per_pipeline_discovery_discovered_augmented_by_static(self):
        self._do_test_per_pipeline_discovery(['discovered_1', 'discovered_2'],
                                             ['static_1', 'static_2'])

    def test_multiple_pipelines_different_static_resources(self):
        # assert that the amalgation of all static resources for a set
        # of pipelines with a common interval is passed to individual
        # pollsters matching those pipelines
        self.pipeline_cfg[0]['resources'] = ['test://']
        self.pipeline_cfg.append({
            'name': "another_pipeline",
            'interval': 60,
            'counters': ['test'],
            'resources': ['another://'],
            'transformers': [],
            'publishers': ["new"],
        })
        self.mgr.discovery_manager = self.create_discovery_manager()
        self.Discovery.resources = []
        self.setup_pipeline()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(1, len(polling_tasks))
        self.assertTrue(60 in polling_tasks.keys())
        self.mgr.interval_task(polling_tasks.get(60))
        self._verify_discovery_params([])
        self.assertEqual(1, len(self.Pollster.samples))
        amalgamated_resources = set(['test://', 'another://'])
        self.assertEqual(amalgamated_resources,
                         set(self.Pollster.samples[0][1]))
        for pipe_line in self.mgr.pipeline_manager.pipelines:
            self.assertEqual(1, len(pipe_line.publishers[0].samples))
            published = pipe_line.publishers[0].samples[0]
            self.assertEqual(amalgamated_resources,
                             set(published.resource_metadata['resources']))

    def test_multiple_sources_different_discoverers(self):
        self.Discovery.resources = ['discovered_1', 'discovered_2']
        self.DiscoveryAnother.resources = ['discovered_3', 'discovered_4']
        sources = [{'name': 'test_source_1',
                    'interval': 60,
                    'counters': ['test'],
                    'discovery': ['testdiscovery'],
                    'sinks': ['test_sink_1']},
                   {'name': 'test_source_2',
                    'interval': 60,
                    'counters': ['testanother'],
                    'discovery': ['testdiscoveryanother'],
                    'sinks': ['test_sink_2']}]
        sinks = [{'name': 'test_sink_1',
                  'transformers': [],
                  'publishers': ['test://']},
                 {'name': 'test_sink_2',
                  'transformers': [],
                  'publishers': ['test://']}]
        self.pipeline_cfg = {'sources': sources, 'sinks': sinks}
        self.mgr.discovery_manager = self.create_discovery_manager()
        self.setup_pipeline()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(1, len(polling_tasks))
        self.assertTrue(60 in polling_tasks.keys())
        self.mgr.interval_task(polling_tasks.get(60))
        self.assertEqual(1, len(self.Pollster.samples))
        self.assertEqual(['discovered_1', 'discovered_2'],
                         self.Pollster.resources)
        self.assertEqual(1, len(self.PollsterAnother.samples))
        self.assertEqual(['discovered_3', 'discovered_4'],
                         self.PollsterAnother.resources)

    def test_multiple_sinks_same_discoverer(self):
        self.Discovery.resources = ['discovered_1', 'discovered_2']
        sources = [{'name': 'test_source_1',
                    'interval': 60,
                    'counters': ['test'],
                    'discovery': ['testdiscovery'],
                    'sinks': ['test_sink_1', 'test_sink_2']}]
        sinks = [{'name': 'test_sink_1',
                  'transformers': [],
                  'publishers': ['test://']},
                 {'name': 'test_sink_2',
                  'transformers': [],
                  'publishers': ['test://']}]
        self.pipeline_cfg = {'sources': sources, 'sinks': sinks}
        self.mgr.discovery_manager = self.create_discovery_manager()
        self.setup_pipeline()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(1, len(polling_tasks))
        self.assertTrue(60 in polling_tasks.keys())
        self.mgr.interval_task(polling_tasks.get(60))
        self.assertEqual(1, len(self.Pollster.samples))
        self.assertEqual(['discovered_1', 'discovered_2'],
                         self.Pollster.resources)

    def test_discovery_partitioning(self):
        self.mgr.discovery_manager = self.create_discovery_manager()
        p_coord = self.mgr.partition_coordinator
        self.pipeline_cfg[0]['discovery'] = ['testdiscovery',
                                             'testdiscoveryanother',
                                             'testdiscoverynonexistent',
                                             'testdiscoveryexception']
        self.setup_pipeline()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(polling_tasks.get(60))
        expected = [mock.call(self.mgr._construct_group_id(d.obj.group_id),
                              d.obj.resources)
                    for d in self.mgr.discovery_manager
                    if hasattr(d.obj, 'resources')]
        self.assertEqual(len(expected),
                         len(p_coord.extract_my_subset.call_args_list))
        for c in expected:
            self.assertIn(c, p_coord.extract_my_subset.call_args_list)
