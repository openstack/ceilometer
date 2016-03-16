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
from oslo_config import fixture as fixture_config
from oslotest import mockpatch
import six
from stevedore import extension

from ceilometer.agent import plugin_base
from ceilometer import pipeline
from ceilometer import publisher
from ceilometer.publisher import test as test_publisher
from ceilometer import sample
from ceilometer.tests import base
from ceilometer import utils


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


class TestPollster(plugin_base.PollsterBase):
    test_data = default_test_data
    discovery = None

    @property
    def default_discovery(self):
        return self.discovery

    def get_samples(self, manager, cache, resources):
        resources = resources or []
        self.samples.append((manager, resources))
        self.resources.extend(resources)
        c = copy.deepcopy(self.test_data)
        c.resource_metadata['resources'] = resources
        return [c]


class BatchTestPollster(TestPollster):
    test_data = default_test_data
    discovery = None

    @property
    def default_discovery(self):
        return self.discovery

    def get_samples(self, manager, cache, resources):
        resources = resources or []
        self.samples.append((manager, resources))
        self.resources.extend(resources)
        for resource in resources:
            c = copy.deepcopy(self.test_data)
            c.timestamp = datetime.datetime.utcnow().isoformat()
            c.resource_id = resource
            c.resource_metadata['resource'] = resource
            yield c


class TestPollsterException(TestPollster):
    def get_samples(self, manager, cache, resources):
        resources = resources or []
        self.samples.append((manager, resources))
        self.resources.extend(resources)
        raise Exception()


class TestDiscovery(plugin_base.DiscoveryBase):
    def discover(self, manager, param=None):
        self.params.append(param)
        return self.resources


class TestDiscoveryException(plugin_base.DiscoveryBase):
    def discover(self, manager, param=None):
        self.params.append(param)
        raise Exception()


@six.add_metaclass(abc.ABCMeta)
class BaseAgentManagerTestCase(base.BaseTestCase):

    class Pollster(TestPollster):
        samples = []
        resources = []
        test_data = default_test_data

    class BatchPollster(BatchTestPollster):
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

    def setup_polling(self):
        self.mgr.polling_manager = pipeline.PollingManager(self.pipeline_cfg)

    def create_extension_list(self):
        return [extension.Extension('test',
                                    None,
                                    None,
                                    self.Pollster(), ),
                extension.Extension('testbatch',
                                    None,
                                    None,
                                    self.BatchPollster(), ),
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

    @mock.patch('ceilometer.pipeline.setup_polling', mock.MagicMock())
    def setUp(self):
        super(BaseAgentManagerTestCase, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.CONF.set_override(
            'pipeline_cfg_file',
            self.path_get('etc/ceilometer/pipeline.yaml')
        )
        self.CONF(args=[])
        self.mgr = self.create_manager()
        self.mgr.extensions = self.create_extension_list()
        self.mgr.partition_coordinator = mock.MagicMock()
        fake_subset = lambda _, x: x
        p_coord = self.mgr.partition_coordinator
        p_coord.extract_my_subset.side_effect = fake_subset
        self.mgr.tg = mock.MagicMock()
        self.pipeline_cfg = {
            'sources': [{
                'name': 'test_pipeline',
                'interval': 60,
                'meters': ['test'],
                'resources': ['test://'] if self.source_resources else [],
                'sinks': ['test_sink']}],
            'sinks': [{
                'name': 'test_sink',
                'transformers': [],
                'publishers': ["test"]}]
        }
        self.setup_polling()
        self.useFixture(mockpatch.PatchObject(
            publisher, 'get_publisher', side_effect=self.get_publisher))

    @staticmethod
    def get_publisher(url, namespace=''):
        fake_drivers = {'test://': test_publisher.TestPublisher,
                        'new://': test_publisher.TestPublisher,
                        'rpc://': test_publisher.TestPublisher}
        return fake_drivers[url](url)

    def tearDown(self):
        self.Pollster.samples = []
        self.Pollster.discovery = []
        self.PollsterAnother.samples = []
        self.PollsterAnother.discovery = []
        self.PollsterException.samples = []
        self.PollsterException.discovery = []
        self.PollsterExceptionAnother.samples = []
        self.PollsterExceptionAnother.discovery = []
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

    @mock.patch('ceilometer.pipeline.setup_polling')
    def test_start(self, setup_polling):
        self.mgr.join_partitioning_groups = mock.MagicMock()
        self.mgr.setup_polling_tasks = mock.MagicMock()
        self.CONF.set_override('heartbeat', 1.0, group='coordination')
        self.mgr.start()
        setup_polling.assert_called_once_with()
        self.mgr.partition_coordinator.start.assert_called_once_with()
        self.mgr.join_partitioning_groups.assert_called_once_with()
        self.mgr.setup_polling_tasks.assert_called_once_with()
        timer_call = mock.call(1.0, self.mgr.partition_coordinator.heartbeat)
        self.assertEqual([timer_call], self.mgr.tg.add_timer.call_args_list)
        self.mgr.stop()
        self.mgr.partition_coordinator.stop.assert_called_once_with()

    @mock.patch('ceilometer.pipeline.setup_polling')
    def test_start_with_pipeline_poller(self, setup_polling):
        self.mgr.join_partitioning_groups = mock.MagicMock()
        self.mgr.setup_polling_tasks = mock.MagicMock()

        self.CONF.set_override('heartbeat', 1.0, group='coordination')
        self.CONF.set_override('refresh_pipeline_cfg', True)
        self.CONF.set_override('pipeline_polling_interval', 5)
        self.mgr.start()
        setup_polling.assert_called_once_with()
        self.mgr.partition_coordinator.start.assert_called_once_with()
        self.mgr.join_partitioning_groups.assert_called_once_with()
        self.mgr.setup_polling_tasks.assert_called_once_with()
        timer_call = mock.call(1.0, self.mgr.partition_coordinator.heartbeat)
        pipeline_poller_call = mock.call(5, self.mgr.refresh_pipeline)
        self.assertEqual([timer_call, pipeline_poller_call],
                         self.mgr.tg.add_timer.call_args_list)

    def test_join_partitioning_groups(self):
        self.mgr.discovery_manager = self.create_discovery_manager()
        self.mgr.join_partitioning_groups()
        p_coord = self.mgr.partition_coordinator
        static_group_ids = [utils.hash_of_set(p['resources'])
                            for p in self.pipeline_cfg['sources']
                            if p['resources']]
        expected = [mock.call(self.mgr.construct_group_id(g))
                    for g in ['another_group', 'global'] + static_group_ids]
        self.assertEqual(len(expected), len(p_coord.join_group.call_args_list))
        for c in expected:
            self.assertIn(c, p_coord.join_group.call_args_list)

    def test_setup_polling_tasks(self):
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(1, len(polling_tasks))
        self.assertIn(60, polling_tasks.keys())
        per_task_resources = polling_tasks[60].resources
        self.assertEqual(1, len(per_task_resources))
        self.assertEqual(set(self.pipeline_cfg['sources'][0]['resources']),
                         set(per_task_resources['test_pipeline-test'].get({})))

    def test_setup_polling_tasks_multiple_interval(self):
        self.pipeline_cfg['sources'].append({
            'name': 'test_pipeline_1',
            'interval': 10,
            'meters': ['test'],
            'resources': ['test://'] if self.source_resources else [],
            'sinks': ['test_sink']
        })
        self.setup_polling()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(2, len(polling_tasks))
        self.assertIn(60, polling_tasks.keys())
        self.assertIn(10, polling_tasks.keys())

    def test_setup_polling_tasks_mismatch_counter(self):
        self.pipeline_cfg['sources'].append({
            'name': 'test_pipeline_1',
            'interval': 10,
            'meters': ['test_invalid'],
            'resources': ['invalid://'],
            'sinks': ['test_sink']
        })
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(1, len(polling_tasks))
        self.assertIn(60, polling_tasks.keys())
        self.assertNotIn(10, polling_tasks.keys())

    def test_setup_polling_task_same_interval(self):
        self.pipeline_cfg['sources'].append({
            'name': 'test_pipeline_1',
            'interval': 60,
            'meters': ['testanother'],
            'resources': ['testanother://'] if self.source_resources else [],
            'sinks': ['test_sink']
        })
        self.setup_polling()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(1, len(polling_tasks))
        pollsters = polling_tasks.get(60).pollster_matches
        self.assertEqual(2, len(pollsters))
        per_task_resources = polling_tasks[60].resources
        self.assertEqual(2, len(per_task_resources))
        key = 'test_pipeline-test'
        self.assertEqual(set(self.pipeline_cfg['sources'][0]['resources']),
                         set(per_task_resources[key].get({})))
        key = 'test_pipeline_1-testanother'
        self.assertEqual(set(self.pipeline_cfg['sources'][1]['resources']),
                         set(per_task_resources[key].get({})))

    def test_agent_manager_start(self):
        mgr = self.create_manager()
        mgr.extensions = self.mgr.extensions
        mgr.create_polling_task = mock.MagicMock()
        mgr.tg = mock.MagicMock()
        mgr.start()
        self.assertTrue(mgr.tg.add_timer.called)

    def test_manager_exception_persistency(self):
        self.pipeline_cfg['sources'].append({
            'name': 'test_pipeline_1',
            'interval': 60,
            'meters': ['testanother'],
            'sinks': ['test_sink']
        })
        self.setup_polling()

    def _verify_discovery_params(self, expected):
        self.assertEqual(expected, self.Discovery.params)
        self.assertEqual(expected, self.DiscoveryAnother.params)
        self.assertEqual(expected, self.DiscoveryException.params)

    def _do_test_per_pollster_discovery(self, discovered_resources,
                                        static_resources):
        self.Pollster.discovery = 'testdiscovery'
        self.mgr.discovery_manager = self.create_discovery_manager()
        self.Discovery.resources = discovered_resources
        self.DiscoveryAnother.resources = [d[::-1]
                                           for d in discovered_resources]
        if static_resources:
            # just so we can test that static + pre_pipeline amalgamated
            # override per_pollster
            self.pipeline_cfg['sources'][0]['discovery'] = [
                'testdiscoveryanother',
                'testdiscoverynonexistent',
                'testdiscoveryexception']
        self.pipeline_cfg['sources'][0]['resources'] = static_resources
        self.setup_polling()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(polling_tasks.get(60))
        if static_resources:
            self.assertEqual(set(static_resources +
                                 self.DiscoveryAnother.resources),
                             set(self.Pollster.resources))
        else:
            self.assertEqual(set(self.Discovery.resources),
                             set(self.Pollster.resources))

        # Make sure no duplicated resource from discovery
        for x in self.Pollster.resources:
            self.assertEqual(1, self.Pollster.resources.count(x))

    def test_per_pollster_discovery(self):
        self._do_test_per_pollster_discovery(['discovered_1', 'discovered_2'],
                                             [])

    def test_per_pollster_discovery_overridden_by_per_pipeline_discovery(self):
        # ensure static+per_source_discovery overrides per_pollster_discovery
        self._do_test_per_pollster_discovery(['discovered_1', 'discovered_2'],
                                             ['static_1', 'static_2'])

    def test_per_pollster_discovery_duplicated(self):
        self._do_test_per_pollster_discovery(['dup', 'discovered_1', 'dup'],
                                             [])

    def test_per_pollster_discovery_overridden_by_duplicated_static(self):
        self._do_test_per_pollster_discovery(['discovered_1', 'discovered_2'],
                                             ['static_1', 'dup', 'dup'])

    def test_per_pollster_discovery_caching(self):
        # ensure single discovery associated with multiple pollsters
        # only called once per polling cycle
        discovered_resources = ['discovered_1', 'discovered_2']
        self.Pollster.discovery = 'testdiscovery'
        self.PollsterAnother.discovery = 'testdiscovery'
        self.mgr.discovery_manager = self.create_discovery_manager()
        self.Discovery.resources = discovered_resources
        self.pipeline_cfg['sources'][0]['meters'].append('testanother')
        self.pipeline_cfg['sources'][0]['resources'] = []
        self.setup_polling()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(polling_tasks.get(60))
        self.assertEqual(1, len(self.Discovery.params))
        self.assertEqual(discovered_resources, self.Pollster.resources)
        self.assertEqual(discovered_resources, self.PollsterAnother.resources)

    def _do_test_per_pipeline_discovery(self,
                                        discovered_resources,
                                        static_resources):
        self.mgr.discovery_manager = self.create_discovery_manager()
        self.Discovery.resources = discovered_resources
        self.DiscoveryAnother.resources = [d[::-1]
                                           for d in discovered_resources]
        self.pipeline_cfg['sources'][0]['discovery'] = [
            'testdiscovery', 'testdiscoveryanother',
            'testdiscoverynonexistent', 'testdiscoveryexception']
        self.pipeline_cfg['sources'][0]['resources'] = static_resources
        self.setup_polling()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(polling_tasks.get(60))
        discovery = self.Discovery.resources + self.DiscoveryAnother.resources
        # compare resource lists modulo ordering
        self.assertEqual(set(static_resources + discovery),
                         set(self.Pollster.resources))

        # Make sure no duplicated resource from discovery
        for x in self.Pollster.resources:
            self.assertEqual(1, self.Pollster.resources.count(x))

    def test_per_pipeline_discovery_discovered_only(self):
        self._do_test_per_pipeline_discovery(['discovered_1', 'discovered_2'],
                                             [])

    def test_per_pipeline_discovery_static_only(self):
        self._do_test_per_pipeline_discovery([],
                                             ['static_1', 'static_2'])

    def test_per_pipeline_discovery_discovered_augmented_by_static(self):
        self._do_test_per_pipeline_discovery(['discovered_1', 'discovered_2'],
                                             ['static_1', 'static_2'])

    def test_per_pipeline_discovery_discovered_duplicated_static(self):
        self._do_test_per_pipeline_discovery(['discovered_1', 'pud'],
                                             ['dup', 'static_1', 'dup'])

    def test_multiple_pipelines_different_static_resources(self):
        # assert that the individual lists of static and discovered resources
        # for each pipeline with a common interval are passed to individual
        # pollsters matching each pipeline
        self.pipeline_cfg['sources'][0]['resources'] = ['test://']
        self.pipeline_cfg['sources'][0]['discovery'] = ['testdiscovery']
        self.pipeline_cfg['sources'].append({
            'name': 'another_pipeline',
            'interval': 60,
            'meters': ['test'],
            'resources': ['another://'],
            'discovery': ['testdiscoveryanother'],
            'sinks': ['test_sink_new']
        })
        self.mgr.discovery_manager = self.create_discovery_manager()
        self.Discovery.resources = ['discovered_1', 'discovered_2']
        self.DiscoveryAnother.resources = ['discovered_3', 'discovered_4']
        self.setup_polling()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(1, len(polling_tasks))
        self.assertIn(60, polling_tasks.keys())
        self.mgr.interval_task(polling_tasks.get(60))
        self.assertEqual([None], self.Discovery.params)
        self.assertEqual([None], self.DiscoveryAnother.params)
        self.assertEqual(2, len(self.Pollster.samples))
        samples = self.Pollster.samples
        test_resources = ['test://', 'discovered_1', 'discovered_2']
        another_resources = ['another://', 'discovered_3', 'discovered_4']
        if samples[0][1] == test_resources:
            self.assertEqual(another_resources, samples[1][1])
        elif samples[0][1] == another_resources:
            self.assertEqual(test_resources, samples[1][1])
        else:
            self.fail('unexpected sample resources %s' % samples)

    def test_multiple_sources_different_discoverers(self):
        self.Discovery.resources = ['discovered_1', 'discovered_2']
        self.DiscoveryAnother.resources = ['discovered_3', 'discovered_4']
        sources = [{'name': 'test_source_1',
                    'interval': 60,
                    'meters': ['test'],
                    'discovery': ['testdiscovery'],
                    'sinks': ['test_sink_1']},
                   {'name': 'test_source_2',
                    'interval': 60,
                    'meters': ['testanother'],
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
        self.setup_polling()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(1, len(polling_tasks))
        self.assertIn(60, polling_tasks.keys())
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
                    'meters': ['test'],
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
        self.setup_polling()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(1, len(polling_tasks))
        self.assertIn(60, polling_tasks.keys())
        self.mgr.interval_task(polling_tasks.get(60))
        self.assertEqual(1, len(self.Pollster.samples))
        self.assertEqual(['discovered_1', 'discovered_2'],
                         self.Pollster.resources)

    def test_discovery_partitioning(self):
        self.mgr.discovery_manager = self.create_discovery_manager()
        p_coord = self.mgr.partition_coordinator
        self.pipeline_cfg['sources'][0]['discovery'] = [
            'testdiscovery', 'testdiscoveryanother',
            'testdiscoverynonexistent', 'testdiscoveryexception']
        self.pipeline_cfg['sources'][0]['resources'] = []
        self.setup_polling()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(polling_tasks.get(60))
        expected = [mock.call(self.mgr.construct_group_id(d.obj.group_id),
                              d.obj.resources)
                    for d in self.mgr.discovery_manager
                    if hasattr(d.obj, 'resources')]
        self.assertEqual(len(expected),
                         len(p_coord.extract_my_subset.call_args_list))
        for c in expected:
            self.assertIn(c, p_coord.extract_my_subset.call_args_list)

    def test_static_resources_partitioning(self):
        p_coord = self.mgr.partition_coordinator
        static_resources = ['static_1', 'static_2']
        static_resources2 = ['static_3', 'static_4']
        self.pipeline_cfg['sources'][0]['resources'] = static_resources
        self.pipeline_cfg['sources'].append({
            'name': 'test_pipeline2',
            'interval': 60,
            'meters': ['test', 'test2'],
            'resources': static_resources2,
            'sinks': ['test_sink']
        })
        # have one pipeline without static resources defined
        self.pipeline_cfg['sources'].append({
            'name': 'test_pipeline3',
            'interval': 60,
            'meters': ['test', 'test2'],
            'resources': [],
            'sinks': ['test_sink']
        })
        self.setup_polling()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(polling_tasks.get(60))
        # Only two groups need to be created, one for each pipeline,
        # even though counter test is used twice
        expected = [mock.call(self.mgr.construct_group_id(
                              utils.hash_of_set(resources)),
                              resources)
                    for resources in [static_resources,
                                      static_resources2]]
        self.assertEqual(len(expected),
                         len(p_coord.extract_my_subset.call_args_list))
        for c in expected:
            self.assertIn(c, p_coord.extract_my_subset.call_args_list)

    @mock.patch('ceilometer.agent.manager.LOG')
    def test_polling_and_notify_with_resources(self, LOG):
        self.setup_polling()
        polling_task = list(self.mgr.setup_polling_tasks().values())[0]
        polling_task.poll_and_notify()
        LOG.info.assert_called_with(
            'Polling pollster %(poll)s in the context of %(src)s',
            {'poll': 'test', 'src': 'test_pipeline'})

    @mock.patch('ceilometer.agent.manager.LOG')
    def test_skip_polling_and_notify_with_no_resources(self, LOG):
        self.pipeline_cfg['sources'][0]['resources'] = []
        self.setup_polling()
        polling_task = list(self.mgr.setup_polling_tasks().values())[0]
        pollster = list(polling_task.pollster_matches['test_pipeline'])[0]
        polling_task.poll_and_notify()
        LOG.info.assert_called_with(
            'Skip pollster %(name)s, no %(p_context)sresources found this '
            'cycle', {'name': pollster.name, 'p_context': ''})

    @mock.patch('ceilometer.agent.manager.LOG')
    def test_skip_polling_polled_resources(self, LOG):
        self.pipeline_cfg['sources'].append({
            'name': 'test_pipeline_1',
            'interval': 60,
            'meters': ['test'],
            'resources': ['test://'],
            'sinks': ['test_sink']
        })
        self.setup_polling()
        polling_task = list(self.mgr.setup_polling_tasks().values())[0]
        polling_task.poll_and_notify()
        LOG.info.assert_called_with(
            'Skip pollster %(name)s, no %(p_context)sresources found this '
            'cycle', {'name': 'test', 'p_context': 'new '})
