#
# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2013 Intel corp.
# Copyright 2013 eNovance
# Copyright 2014 Red Hat, Inc
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
import copy
import datetime
import fixtures
import mock

from keystoneauth1 import exceptions as ka_exceptions
from stevedore import extension

from ceilometer.compute import discovery as nova_discover
from ceilometer.hardware import discovery
from ceilometer.polling import manager
from ceilometer.polling import plugin_base
from ceilometer import sample
from ceilometer import service
from ceilometer.tests import base


def default_test_data(name='test'):
    return sample.Sample(
        name=name,
        type=sample.TYPE_CUMULATIVE,
        unit='',
        volume=1,
        user_id='test',
        project_id='test',
        resource_id='test_run_tasks',
        timestamp=datetime.datetime.utcnow().isoformat(),
        resource_metadata={'name': 'Pollster'})


class TestPollster(plugin_base.PollsterBase):
    test_data = default_test_data()
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


class PollingException(Exception):
    pass


class TestPollsterBuilder(TestPollster):
    @classmethod
    def build_pollsters(cls, conf):
        return [('builder1', cls(conf)), ('builder2', cls(conf))]


class TestManager(base.BaseTestCase):
    def setUp(self):
        super(TestManager, self).setUp()
        self.conf = service.prepare_service([], [])

    def test_hash_of_set(self):
        x = ['a', 'b']
        y = ['a', 'b', 'a']
        z = ['a', 'c']
        self.assertEqual(manager.hash_of_set(x), manager.hash_of_set(y))
        self.assertNotEqual(manager.hash_of_set(x), manager.hash_of_set(z))
        self.assertNotEqual(manager.hash_of_set(y), manager.hash_of_set(z))

    def test_load_plugins(self):
        mgr = manager.AgentManager(0, self.conf)
        self.assertIsNotNone(list(mgr.extensions))

    # Test plugin load behavior based on Node Manager pollsters.
    @mock.patch('ceilometer.ipmi.pollsters.node._Base.__init__',
                mock.Mock(return_value=None))
    @mock.patch('ceilometer.ipmi.pollsters.sensor.SensorPollster.__init__',
                mock.Mock(return_value=None))
    def test_load_normal_plugins(self):
        mgr = manager.AgentManager(0, self.conf,
                                   namespaces=['ipmi'])
        # 8 pollsters for Node Manager
        self.assertEqual(12, len(mgr.extensions))

    # Skip loading pollster upon ExtensionLoadError
    @mock.patch('ceilometer.ipmi.pollsters.node._Base.__init__',
                mock.Mock(side_effect=plugin_base.ExtensionLoadError(
                    'NodeManager not supported on host')))
    @mock.patch('ceilometer.polling.manager.LOG')
    def test_load_failed_plugins(self, LOG):
        # Here we additionally check that namespaces will be converted to the
        # list if param was not set as a list.
        manager.AgentManager(0, self.conf, namespaces='ipmi')
        err_msg = 'Skip loading extension for %s: %s'
        pollster_names = [
            'power', 'temperature', 'outlet_temperature',
            'airflow', 'cups', 'cpu_util', 'mem_util', 'io_util']
        calls = [mock.call(err_msg, 'hardware.ipmi.node.%s' % n,
                           'NodeManager not supported on host')
                 for n in pollster_names]
        LOG.debug.assert_has_calls(calls=calls[:2], any_order=True)

    # Skip loading pollster upon ImportError
    @mock.patch('ceilometer.ipmi.pollsters.node._Base.__init__',
                mock.Mock(side_effect=ImportError))
    @mock.patch('ceilometer.ipmi.pollsters.sensor.SensorPollster.__init__',
                mock.Mock(side_effect=ImportError))
    @mock.patch('ceilometer.polling.manager.LOG')
    def test_import_error_in_plugin(self, LOG):
        namespaces = ['ipmi']
        manager.AgentManager(0, self.conf, namespaces=namespaces)
        LOG.warning.assert_called_with(
            'No valid pollsters can be loaded from %s namespaces', namespaces)

    # Exceptions other than ExtensionLoadError are propagated
    @mock.patch('ceilometer.ipmi.pollsters.node._Base.__init__',
                mock.Mock(side_effect=PollingException))
    @mock.patch('ceilometer.ipmi.pollsters.sensor.SensorPollster.__init__',
                mock.Mock(side_effect=PollingException))
    def test_load_exceptional_plugins(self):
        self.assertRaises(PollingException,
                          manager.AgentManager,
                          0, self.conf,
                          ['ipmi'])

    def test_builder(self):
        @staticmethod
        def fake_get_ext_mgr(namespace, *args, **kwargs):
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
                                            TestPollster(self.conf)),
                    ]
                )

        with mock.patch.object(manager.AgentManager, '_get_ext_mgr',
                               new=fake_get_ext_mgr):
            mgr = manager.AgentManager(0, self.conf, namespaces=['central'])
            self.assertEqual(3, len(mgr.extensions))
            for ext in mgr.extensions:
                self.assertIn(ext.name, ['builder1', 'builder2', 'test'])
                self.assertIsInstance(ext.obj, TestPollster)


class BatchTestPollster(TestPollster):
    test_data = default_test_data()
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


class TestPollsterKeystone(TestPollster):
    def get_samples(self, manager, cache, resources):
        # Just try to use keystone, that will raise an exception
        manager.keystone.projects.list()


class TestPollsterPollingException(TestPollster):
    discovery = 'test'
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


class TestDiscovery(plugin_base.DiscoveryBase):
    def discover(self, manager, param=None):
        self.params.append(param)
        return self.resources


class TestDiscoveryException(plugin_base.DiscoveryBase):
    def discover(self, manager, param=None):
        self.params.append(param)
        raise Exception()


class BaseAgent(base.BaseTestCase):

    class Pollster(TestPollster):
        samples = []
        resources = []
        test_data = default_test_data()

    class BatchPollster(BatchTestPollster):
        samples = []
        resources = []
        test_data = default_test_data()

    class PollsterAnother(TestPollster):
        samples = []
        resources = []
        test_data = default_test_data('testanother')

    class PollsterKeystone(TestPollsterKeystone):
        samples = []
        resources = []
        test_data = default_test_data('testkeystone')

    class PollsterPollingException(TestPollsterPollingException):
        samples = []
        resources = []
        test_data = default_test_data('testpollingexception')

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

    def setup_polling(self, poll_cfg=None):
        name = self.cfg2file(poll_cfg or self.polling_cfg)
        self.CONF.set_override('cfg_file', name, group='polling')
        self.mgr.polling_manager = manager.PollingManager(self.CONF)

    def create_manager(self):
        return manager.AgentManager(0, self.CONF)

    def fake_notifier_sample(self, ctxt, event_type, payload):
        for m in payload['samples']:
            del m['message_signature']
            self.notified_samples.append(m)

    def setUp(self):
        super(BaseAgent, self).setUp()
        self.notified_samples = []
        self.notifier = mock.Mock()
        self.notifier.sample.side_effect = self.fake_notifier_sample
        self.useFixture(fixtures.MockPatch('oslo_messaging.Notifier',
                                           return_value=self.notifier))
        self.useFixture(fixtures.MockPatch('keystoneclient.v2_0.client.Client',
                                           return_value=mock.Mock()))
        self.CONF = service.prepare_service([], [])
        self.CONF.set_override(
            'cfg_file',
            self.path_get('etc/ceilometer/polling_all.yaml'), group='polling'
        )
        self.polling_cfg = {
            'sources': [{
                'name': 'test_polling',
                'interval': 60,
                'meters': ['test'],
                'resources': ['test://']}]
        }

    def tearDown(self):
        self.PollsterKeystone.samples = []
        self.PollsterKeystone.resources = []
        self.PollsterPollingException.samples = []
        self.PollsterPollingException.resources = []
        self.Pollster.samples = []
        self.Pollster.discovery = []
        self.PollsterAnother.samples = []
        self.PollsterAnother.discovery = []
        self.Pollster.resources = []
        self.PollsterAnother.resources = []
        self.Discovery.params = []
        self.DiscoveryAnother.params = []
        self.DiscoveryException.params = []
        self.Discovery.resources = []
        self.DiscoveryAnother.resources = []
        super(BaseAgent, self).tearDown()

    def create_extension_list(self):
        return [extension.Extension('test',
                                    None,
                                    None,
                                    self.Pollster(self.CONF), ),
                extension.Extension('testbatch',
                                    None,
                                    None,
                                    self.BatchPollster(self.CONF), ),
                extension.Extension('testanother',
                                    None,
                                    None,
                                    self.PollsterAnother(self.CONF), ),
                extension.Extension('testkeystone',
                                    None,
                                    None,
                                    self.PollsterKeystone(self.CONF), ),
                extension.Extension('testpollingexception',
                                    None,
                                    None,
                                    self.PollsterPollingException(self.CONF), )
                ]

    def create_discoveries(self):
        return extension.ExtensionManager.make_test_instance(
            [
                extension.Extension(
                    'testdiscovery',
                    None,
                    None,
                    self.Discovery(self.CONF), ),
                extension.Extension(
                    'testdiscoveryanother',
                    None,
                    None,
                    self.DiscoveryAnother(self.CONF), ),
                extension.Extension(
                    'testdiscoveryexception',
                    None,
                    None,
                    self.DiscoveryException(self.CONF), ),
            ],
        )


class TestPollingAgent(BaseAgent):

    def setUp(self):
        super(TestPollingAgent, self).setUp()
        self.mgr = self.create_manager()
        self.mgr.extensions = self.create_extension_list()
        self.setup_polling()

    @mock.patch('ceilometer.polling.manager.PollingManager')
    def test_start(self, poll_manager):
        self.mgr.setup_polling_tasks = mock.MagicMock()
        self.mgr.run()
        poll_manager.assert_called_once_with(self.CONF)
        self.mgr.setup_polling_tasks.assert_called_once_with()
        self.mgr.terminate()

    def test_setup_polling_tasks(self):
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(1, len(polling_tasks))
        self.assertIn(60, polling_tasks.keys())
        per_task_resources = polling_tasks[60].resources
        self.assertEqual(1, len(per_task_resources))
        self.assertEqual(set(self.polling_cfg['sources'][0]['resources']),
                         set(per_task_resources['test_polling-test'].get({})))

    def test_setup_polling_tasks_multiple_interval(self):
        self.polling_cfg['sources'].append({
            'name': 'test_polling_1',
            'interval': 10,
            'meters': ['test'],
            'resources': ['test://'],
        })
        self.setup_polling()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(2, len(polling_tasks))
        self.assertIn(60, polling_tasks.keys())
        self.assertIn(10, polling_tasks.keys())

    def test_setup_polling_tasks_mismatch_counter(self):
        self.polling_cfg['sources'].append({
            'name': 'test_polling_1',
            'interval': 10,
            'meters': ['test_invalid'],
            'resources': ['invalid://'],
        })
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(1, len(polling_tasks))
        self.assertIn(60, polling_tasks.keys())
        self.assertNotIn(10, polling_tasks.keys())

    def test_setup_polling_task_same_interval(self):
        self.polling_cfg['sources'].append({
            'name': 'test_polling_1',
            'interval': 60,
            'meters': ['testanother'],
            'resources': ['testanother://'],
        })
        self.setup_polling()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.assertEqual(1, len(polling_tasks))
        pollsters = polling_tasks.get(60).pollster_matches
        self.assertEqual(2, len(pollsters))
        per_task_resources = polling_tasks[60].resources
        self.assertEqual(2, len(per_task_resources))
        key = 'test_polling-test'
        self.assertEqual(set(self.polling_cfg['sources'][0]['resources']),
                         set(per_task_resources[key].get({})))
        key = 'test_polling_1-testanother'
        self.assertEqual(set(self.polling_cfg['sources'][1]['resources']),
                         set(per_task_resources[key].get({})))

    def _verify_discovery_params(self, expected):
        self.assertEqual(expected, self.Discovery.params)
        self.assertEqual(expected, self.DiscoveryAnother.params)
        self.assertEqual(expected, self.DiscoveryException.params)

    def _do_test_per_pollster_discovery(self, discovered_resources,
                                        static_resources):
        self.Pollster.discovery = 'testdiscovery'
        self.mgr.discoveries = self.create_discoveries()
        self.Discovery.resources = discovered_resources
        self.DiscoveryAnother.resources = [d[::-1]
                                           for d in discovered_resources]
        if static_resources:
            # just so we can test that static + pre_polling amalgamated
            # override per_pollster
            self.polling_cfg['sources'][0]['discovery'] = [
                'testdiscoveryanother',
                'testdiscoverynonexistent',
                'testdiscoveryexception']
        self.polling_cfg['sources'][0]['resources'] = static_resources
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

    def test_per_pollster_discovery_overridden_by_per_polling_discovery(self):
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
        self.mgr.discoveries = self.create_discoveries()
        self.Discovery.resources = discovered_resources
        self.polling_cfg['sources'][0]['meters'].append('testanother')
        self.polling_cfg['sources'][0]['resources'] = []
        self.setup_polling()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(polling_tasks.get(60))
        self.assertEqual(1, len(self.Discovery.params))
        self.assertEqual(discovered_resources, self.Pollster.resources)
        self.assertEqual(discovered_resources, self.PollsterAnother.resources)

    def _do_test_per_polling_discovery(self, discovered_resources,
                                       static_resources):
        self.mgr.discoveries = self.create_discoveries()
        self.Discovery.resources = discovered_resources
        self.DiscoveryAnother.resources = [d[::-1]
                                           for d in discovered_resources]
        self.polling_cfg['sources'][0]['discovery'] = [
            'testdiscovery', 'testdiscoveryanother',
            'testdiscoverynonexistent', 'testdiscoveryexception']
        self.polling_cfg['sources'][0]['resources'] = static_resources
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

    def test_per_polling_discovery_discovered_only(self):
        self._do_test_per_polling_discovery(['discovered_1', 'discovered_2'],
                                            [])

    def test_per_polling_discovery_static_only(self):
        self._do_test_per_polling_discovery([], ['static_1', 'static_2'])

    def test_per_polling_discovery_discovered_augmented_by_static(self):
        self._do_test_per_polling_discovery(['discovered_1', 'discovered_2'],
                                            ['static_1', 'static_2'])

    def test_per_polling_discovery_discovered_duplicated_static(self):
        self._do_test_per_polling_discovery(['discovered_1', 'pud'],
                                            ['dup', 'static_1', 'dup'])

    def test_multiple_pollings_different_static_resources(self):
        # assert that the individual lists of static and discovered resources
        # for each polling with a common interval are passed to individual
        # pollsters matching each polling
        self.polling_cfg['sources'][0]['resources'] = ['test://']
        self.polling_cfg['sources'][0]['discovery'] = ['testdiscovery']
        self.polling_cfg['sources'].append({
            'name': 'another_polling',
            'interval': 60,
            'meters': ['test'],
            'resources': ['another://'],
            'discovery': ['testdiscoveryanother'],
        })
        self.mgr.discoveries = self.create_discoveries()
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
                    'discovery': ['testdiscovery']},
                   {'name': 'test_source_2',
                    'interval': 60,
                    'meters': ['testanother'],
                    'discovery': ['testdiscoveryanother']}]
        self.polling_cfg = {'sources': sources}
        self.mgr.discoveries = self.create_discoveries()
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

    @mock.patch('ceilometer.polling.manager.LOG')
    def test_polling_and_notify_with_resources(self, LOG):
        self.setup_polling()
        polling_task = list(self.mgr.setup_polling_tasks().values())[0]
        polling_task.poll_and_notify()
        LOG.info.assert_called_with(
            'Polling pollster %(poll)s in the context of %(src)s',
            {'poll': 'test', 'src': 'test_polling'})

    @mock.patch('ceilometer.polling.manager.LOG')
    def test_skip_polling_and_notify_with_no_resources(self, LOG):
        self.polling_cfg['sources'][0]['resources'] = []
        self.setup_polling()
        polling_task = list(self.mgr.setup_polling_tasks().values())[0]
        pollster = list(polling_task.pollster_matches['test_polling'])[0]
        polling_task.poll_and_notify()
        LOG.debug.assert_called_with(
            'Skip pollster %(name)s, no %(p_context)sresources found this '
            'cycle', {'name': pollster.name, 'p_context': ''})

    @mock.patch('ceilometer.polling.manager.LOG')
    def test_skip_polling_polled_resources(self, LOG):
        self.polling_cfg['sources'].append({
            'name': 'test_polling_1',
            'interval': 60,
            'meters': ['test'],
            'resources': ['test://'],
        })
        self.setup_polling()
        polling_task = list(self.mgr.setup_polling_tasks().values())[0]
        polling_task.poll_and_notify()
        LOG.debug.assert_called_with(
            'Skip pollster %(name)s, no %(p_context)sresources found this '
            'cycle', {'name': 'test', 'p_context': 'new '})

    @mock.patch('oslo_utils.timeutils.utcnow')
    def test_polling_samples_timestamp(self, mock_utc):
        polled_samples = []
        timestamp = '2222-11-22T00:11:22.333333'

        def fake_send_notification(samples):
            polled_samples.extend(samples)

        mock_utc.return_value = datetime.datetime.strptime(
            timestamp, "%Y-%m-%dT%H:%M:%S.%f")

        self.setup_polling()
        polling_task = list(self.mgr.setup_polling_tasks().values())[0]
        polling_task._send_notification = mock.Mock(
            side_effect=fake_send_notification)
        polling_task.poll_and_notify()
        self.assertEqual(timestamp, polled_samples[0]['timestamp'])

    def test_get_sample_resources(self):
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(list(polling_tasks.values())[0])
        self.assertTrue(self.Pollster.resources)

    def test_when_keystone_fail(self):
        """Test for bug 1316532."""
        self.useFixture(fixtures.MockPatch(
            'keystoneclient.v2_0.client.Client',
            side_effect=ka_exceptions.ClientException))
        poll_cfg = {
            'sources': [{
                'name': "test_keystone",
                'interval': 10,
                'meters': ['testkeystone'],
                'resources': ['test://'],
                'sinks': ['test_sink']}],
            'sinks': [{
                'name': 'test_sink',
                'publishers': ["test"]}]
        }
        self.setup_polling(poll_cfg)
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(list(polling_tasks.values())[0])
        self.assertFalse(self.PollsterKeystone.samples)
        self.assertFalse(self.notified_samples)

    @mock.patch('ceilometer.polling.manager.LOG')
    @mock.patch('ceilometer.nova_client.LOG')
    def test_hardware_discover_fail_minimize_logs(self, novalog, baselog):
        class PollsterHardware(TestPollster):
            discovery = 'tripleo_overcloud_nodes'

        class PollsterHardwareAnother(TestPollster):
            discovery = 'tripleo_overcloud_nodes'

        self.mgr.extensions.extend([
            extension.Extension('testhardware',
                                None,
                                None,
                                PollsterHardware(self.CONF), ),
            extension.Extension('testhardware2',
                                None,
                                None,
                                PollsterHardwareAnother(self.CONF), )
        ])
        ext = extension.Extension('tripleo_overcloud_nodes',
                                  None,
                                  None,
                                  discovery.NodesDiscoveryTripleO(self.CONF))
        self.mgr.discoveries = (extension.ExtensionManager
                                .make_test_instance([ext]))

        poll_cfg = {
            'sources': [{
                'name': "test_hardware",
                'interval': 10,
                'meters': ['testhardware', 'testhardware2'],
                'sinks': ['test_sink']}],
            'sinks': [{
                'name': 'test_sink',
                'publishers': ["test"]}]
        }
        self.setup_polling(poll_cfg)
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(list(polling_tasks.values())[0])
        self.assertEqual(1, novalog.exception.call_count)
        self.assertFalse(baselog.exception.called)

    @mock.patch('ceilometer.polling.manager.LOG')
    def test_polling_exception(self, LOG):
        source_name = 'test_pollingexception'
        res_list = ['test://']
        poll_cfg = {
            'sources': [{
                'name': source_name,
                'interval': 10,
                'meters': ['testpollingexception'],
                'resources': res_list,
                'sinks': ['test_sink']}],
            'sinks': [{
                'name': 'test_sink',
                'publishers': ["test"]}]
        }
        self.setup_polling(poll_cfg)
        polling_task = list(self.mgr.setup_polling_tasks().values())[0]
        pollster = list(polling_task.pollster_matches[source_name])[0]

        # 2 samples after 4 pollings, as pollster got disabled upon exception
        for x in range(0, 4):
            self.mgr.interval_task(polling_task)
        samples = self.notified_samples
        self.assertEqual(2, len(samples))
        LOG.error.assert_called_once_with((
            'Prevent pollster %(name)s from '
            'polling %(res_list)s on source %(source)s anymore!'),
            dict(name=pollster.name, res_list=str(res_list),
                 source=source_name))

    @mock.patch('ceilometer.polling.manager.LOG')
    def test_polling_novalike_exception(self, LOG):
        source_name = 'test_pollingexception'
        poll_cfg = {
            'sources': [{
                'name': source_name,
                'interval': 10,
                'meters': ['testpollingexception'],
                'sinks': ['test_sink']}],
            'sinks': [{
                'name': 'test_sink',
                'publishers': ["test"]}]
        }
        self.setup_polling(poll_cfg)
        polling_task = list(self.mgr.setup_polling_tasks().values())[0]
        pollster = list(polling_task.pollster_matches[source_name])[0]

        with mock.patch.object(polling_task.manager, 'discover') as disco:
            # NOTE(gordc): polling error on 3rd poll
            for __ in range(4):
                disco.return_value = (
                    [nova_discover.NovaLikeServer(**{'id': 1})])
                self.mgr.interval_task(polling_task)
        LOG.error.assert_called_once_with((
            'Prevent pollster %(name)s from '
            'polling %(res_list)s on source %(source)s anymore!'),
            dict(name=pollster.name,
                 res_list="[<NovaLikeServer: unknown-name>]",
                 source=source_name))

    def test_batching_polled_samples_disable_batch(self):
        self.CONF.set_override('batch_size', 0, group='polling')
        self._batching_samples(4, 4)

    def test_batching_polled_samples_batch_size(self):
        self.CONF.set_override('batch_size', 2, group='polling')
        self._batching_samples(4, 2)

    def test_batching_polled_samples_default(self):
        self._batching_samples(4, 1)

    def _batching_samples(self, expected_samples, call_count):
        poll_cfg = {
            'sources': [{
                'name': 'test_pipeline',
                'interval': 1,
                'meters': ['testbatch'],
                'resources': ['alpha', 'beta', 'gamma', 'delta'],
                'sinks': ['test_sink']}],
            'sinks': [{
                'name': 'test_sink',
                'publishers': ["test"]}]
        }
        self.setup_polling(poll_cfg)
        polling_task = list(self.mgr.setup_polling_tasks().values())[0]

        self.mgr.interval_task(polling_task)
        samples = self.notified_samples
        self.assertEqual(expected_samples, len(samples))
        self.assertEqual(call_count, self.notifier.sample.call_count)


class TestPollingAgentPartitioned(BaseAgent):

    def setUp(self):
        super(TestPollingAgentPartitioned, self).setUp()
        self.CONF.set_override("backend_url", "zake://", "coordination")
        self.hashring = mock.MagicMock()
        self.hashring.belongs_to_self = mock.MagicMock()
        self.hashring.belongs_to_self.return_value = True

        self.mgr = self.create_manager()
        self.mgr.extensions = self.create_extension_list()
        self.mgr.hashrings = mock.MagicMock()
        self.mgr.hashrings.__getitem__.return_value = self.hashring
        self.setup_polling()

    def test_discovery_partitioning(self):
        discovered_resources = ['discovered_1', 'discovered_2']
        self.Pollster.discovery = 'testdiscovery'
        self.mgr.discoveries = self.create_discoveries()
        self.Discovery.resources = discovered_resources
        self.polling_cfg['sources'][0]['discovery'] = [
            'testdiscovery', 'testdiscoveryanother',
            'testdiscoverynonexistent', 'testdiscoveryexception']
        self.polling_cfg['sources'][0]['resources'] = []
        self.setup_polling()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(polling_tasks.get(60))
        self.hashring.belongs_to_self.assert_has_calls(
            [mock.call('discovered_1'), mock.call('discovered_2')])

    def test_discovery_partitioning_unhashable(self):
        discovered_resources = [{'unhashable': True}]
        self.Pollster.discovery = 'testdiscovery'
        self.mgr.discoveries = self.create_discoveries()
        self.Discovery.resources = discovered_resources
        self.polling_cfg['sources'][0]['discovery'] = [
            'testdiscovery', 'testdiscoveryanother',
            'testdiscoverynonexistent', 'testdiscoveryexception']
        self.polling_cfg['sources'][0]['resources'] = []
        self.setup_polling()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(polling_tasks.get(60))
        self.hashring.belongs_to_self.assert_has_calls(
            [mock.call('{\'unhashable\': True}')])

    def test_static_resources_partitioning(self):
        static_resources = ['static_1', 'static_2']
        static_resources2 = ['static_3', 'static_4']
        self.polling_cfg['sources'][0]['resources'] = static_resources
        self.polling_cfg['sources'].append({
            'name': 'test_polling2',
            'interval': 60,
            'meters': ['test', 'test2'],
            'resources': static_resources2,
        })
        # have one polling without static resources defined
        self.polling_cfg['sources'].append({
            'name': 'test_polling3',
            'interval': 60,
            'meters': ['test', 'test2'],
            'resources': [],
        })
        self.setup_polling()
        polling_tasks = self.mgr.setup_polling_tasks()
        self.mgr.interval_task(polling_tasks.get(60))
        self.hashring.belongs_to_self.assert_has_calls([
            mock.call('static_1'),
            mock.call('static_2'),
            mock.call('static_3'),
            mock.call('static_4'),
        ], any_order=True)
