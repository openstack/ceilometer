#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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
"""Tests for Ceilometer notify daemon."""

import shutil
import time

import mock
from oslo_config import fixture as fixture_config
import oslo_messaging
from oslo_utils import fileutils
import six
from stevedore import extension
import yaml

from ceilometer.agent import plugin_base
from ceilometer import messaging
from ceilometer import notification
from ceilometer.publisher import test as test_publisher
from ceilometer.tests import base as tests_base

TEST_NOTICE_CTXT = {
    u'auth_token': u'3d8b13de1b7d499587dfc69b77dc09c2',
    u'is_admin': True,
    u'project_id': u'7c150a59fe714e6f9263774af9688f0e',
    u'quota_class': None,
    u'read_deleted': u'no',
    u'remote_address': u'10.0.2.15',
    u'request_id': u'req-d68b36e0-9233-467f-9afb-d81435d64d66',
    u'roles': [u'admin'],
    u'timestamp': u'2012-05-08T20:23:41.425105',
    u'user_id': u'1e3ce043029547f1a61c1996d1a531a2',
}

TEST_NOTICE_METADATA = {
    u'message_id': u'dae6f69c-00e0-41c0-b371-41ec3b7f4451',
    u'timestamp': u'2012-05-08 20:23:48.028195',
}

TEST_NOTICE_PAYLOAD = {
    u'created_at': u'2012-05-08 20:23:41',
    u'deleted_at': u'',
    u'disk_gb': 0,
    u'display_name': u'testme',
    u'fixed_ips': [{u'address': u'10.0.0.2',
                    u'floating_ips': [],
                    u'meta': {},
                    u'type': u'fixed',
                    u'version': 4}],
    u'image_ref_url': u'http://10.0.2.15:9292/images/UUID',
    u'instance_id': u'9f9d01b9-4a58-4271-9e27-398b21ab20d1',
    u'instance_type': u'm1.tiny',
    u'instance_type_id': 2,
    u'launched_at': u'2012-05-08 20:23:47.985999',
    u'memory_mb': 512,
    u'state': u'active',
    u'state_description': u'',
    u'tenant_id': u'7c150a59fe714e6f9263774af9688f0e',
    u'user_id': u'1e3ce043029547f1a61c1996d1a531a2',
    u'reservation_id': u'1e3ce043029547f1a61c1996d1a531a3',
    u'vcpus': 1,
    u'root_gb': 0,
    u'ephemeral_gb': 0,
    u'host': u'compute-host-name',
    u'availability_zone': u'1e3ce043029547f1a61c1996d1a531a4',
    u'os_type': u'linux?',
    u'architecture': u'x86',
    u'image_ref': u'UUID',
    u'kernel_id': u'1e3ce043029547f1a61c1996d1a531a5',
    u'ramdisk_id': u'1e3ce043029547f1a61c1996d1a531a6',
}


class _FakeNotificationPlugin(plugin_base.NotificationBase):
    event_types = ['fake.event']

    def get_targets(self, conf):
        return [oslo_messaging.Target(
            topic=topic, exchange=conf.nova_control_exchange)
            for topic in self.get_notification_topics(conf)]

    def process_notification(self, message):
        return []


class TestNotification(tests_base.BaseTestCase):

    def setUp(self):
        super(TestNotification, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.CONF.set_override("connection", "log://", group='database')
        self.CONF.set_override("backend_url", None, group="coordination")
        self.CONF.set_override("disable_non_metric_meters", False,
                               group="notification")
        self.CONF.set_override("workload_partitioning", True,
                               group='notification')
        self.setup_messaging(self.CONF)
        self.srv = notification.NotificationService(0, self.CONF)

    def fake_get_notifications_manager(self, pm):
        self.plugin = _FakeNotificationPlugin(pm)
        return extension.ExtensionManager.make_test_instance(
            [
                extension.Extension('test',
                                    None,
                                    None,
                                    self.plugin)
            ]
        )

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    @mock.patch('ceilometer.pipeline.setup_event_pipeline', mock.MagicMock())
    @mock.patch('ceilometer.event.endpoint.EventsNotificationEndpoint')
    def _do_process_notification_manager_start(self,
                                               fake_event_endpoint_class):
        self.CONF([], project='ceilometer', validate_default_values=True)
        with mock.patch.object(self.srv,
                               '_get_notifications_manager') as get_nm:
            get_nm.side_effect = self.fake_get_notifications_manager
            self.srv.run()
        self.addCleanup(self.srv.terminate)
        self.fake_event_endpoint = fake_event_endpoint_class.return_value

    def test_start_multiple_listeners(self):
        urls = ["fake://vhost1", "fake://vhost2"]
        self.CONF.set_override("messaging_urls", urls, group="notification")
        self._do_process_notification_manager_start()
        self.assertEqual(2, len(self.srv.listeners))

    def test_process_notification(self):
        self._do_process_notification_manager_start()
        self.srv.pipeline_manager.pipelines[0] = mock.MagicMock()

        self.plugin.info([{'ctxt': TEST_NOTICE_CTXT,
                           'publisher_id': 'compute.vagrant-precise',
                           'event_type': 'compute.instance.create.end',
                           'payload': TEST_NOTICE_PAYLOAD,
                           'metadata': TEST_NOTICE_METADATA}])

        self.assertEqual(2, len(self.srv.listeners[0].dispatcher.endpoints))

    @mock.patch('ceilometer.pipeline.setup_event_pipeline', mock.MagicMock())
    def test_process_notification_with_events(self):
        self._do_process_notification_manager_start()
        self.assertEqual(2, len(self.srv.listeners[0].dispatcher.endpoints))
        self.assertEqual(self.fake_event_endpoint,
                         self.srv.listeners[0].dispatcher.endpoints[0])

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    @mock.patch('ceilometer.pipeline.setup_event_pipeline', mock.MagicMock())
    @mock.patch('oslo_messaging.get_batch_notification_listener')
    def test_unique_consumers(self, mock_listener):

        def fake_get_notifications_manager_dup_targets(pm):
            plugin = _FakeNotificationPlugin(pm)
            return extension.ExtensionManager.make_test_instance(
                [extension.Extension('test', None, None, plugin),
                 extension.Extension('test', None, None, plugin)])

        self.CONF([], project='ceilometer', validate_default_values=True)
        with mock.patch.object(self.srv,
                               '_get_notifications_manager') as get_nm:
            get_nm.side_effect = fake_get_notifications_manager_dup_targets
            self.srv.run()
            self.addCleanup(self.srv.terminate)
            self.assertEqual(2, len(mock_listener.call_args_list))
            args, kwargs = mock_listener.call_args
            self.assertEqual(1, len(self.srv.listeners))


class BaseRealNotification(tests_base.BaseTestCase):
    def setup_pipeline(self, counter_names):
        pipeline = yaml.dump({
            'sources': [{
                'name': 'test_pipeline',
                'interval': 5,
                'meters': counter_names,
                'sinks': ['test_sink']
            }],
            'sinks': [{
                'name': 'test_sink',
                'transformers': [],
                'publishers': ['test://']
            }]
        })
        if six.PY3:
            pipeline = pipeline.encode('utf-8')

        pipeline_cfg_file = fileutils.write_to_tempfile(content=pipeline,
                                                        prefix="pipeline",
                                                        suffix="yaml")
        return pipeline_cfg_file

    def setup_event_pipeline(self, event_names):
        ev_pipeline = yaml.dump({
            'sources': [{
                'name': 'test_event',
                'events': event_names,
                'sinks': ['test_sink']
            }],
            'sinks': [{
                'name': 'test_sink',
                'publishers': ['test://']
            }]
        })
        if six.PY3:
            ev_pipeline = ev_pipeline.encode('utf-8')

        ev_pipeline_cfg_file = fileutils.write_to_tempfile(
            content=ev_pipeline, prefix="event_pipeline", suffix="yaml")
        return ev_pipeline_cfg_file

    def setUp(self):
        super(BaseRealNotification, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf
        # Dummy config file to avoid looking for system config
        self.CONF([], project='ceilometer', validate_default_values=True)
        self.setup_messaging(self.CONF, 'nova')

        pipeline_cfg_file = self.setup_pipeline(['vcpus', 'memory'])
        self.CONF.set_override("pipeline_cfg_file", pipeline_cfg_file)

        self.expected_samples = 2

        self.CONF.set_override("backend_url", None, group="coordination")

        ev_pipeline_cfg_file = self.setup_event_pipeline(
            ['compute.instance.*'])
        self.expected_events = 1

        self.CONF.set_override("event_pipeline_cfg_file",
                               ev_pipeline_cfg_file)
        self.CONF.set_override(
            "definitions_cfg_file",
            self.path_get('etc/ceilometer/event_definitions.yaml'),
            group='event')
        self.publisher = test_publisher.TestPublisher(self.CONF, "")

    def _check_notification_service(self):
        self.srv.run()
        self.addCleanup(self.srv.terminate)

        notifier = messaging.get_notifier(self.transport,
                                          "compute.vagrant-precise")
        notifier.info({}, 'compute.instance.create.end',
                      TEST_NOTICE_PAYLOAD)
        start = time.time()
        while time.time() - start < 60:
            if (len(self.publisher.samples) >= self.expected_samples and
                    len(self.publisher.events) >= self.expected_events):
                break

        resources = list(set(s.resource_id for s in self.publisher.samples))
        self.assertEqual(self.expected_samples, len(self.publisher.samples))
        self.assertEqual(self.expected_events, len(self.publisher.events))
        self.assertEqual(["9f9d01b9-4a58-4271-9e27-398b21ab20d1"], resources)


class TestRealNotificationReloadablePipeline(BaseRealNotification):

    def setUp(self):
        super(TestRealNotificationReloadablePipeline, self).setUp()
        self.CONF.set_override('refresh_pipeline_cfg', True)
        self.CONF.set_override('refresh_event_pipeline_cfg', True)
        self.CONF.set_override('pipeline_polling_interval', 1)
        self.srv = notification.NotificationService(0, self.CONF)

    @mock.patch('ceilometer.publisher.test.TestPublisher')
    def test_notification_pipeline_poller(self, fake_publisher_cls):
        fake_publisher_cls.return_value = self.publisher
        self.srv.run()
        self.addCleanup(self.srv.terminate)
        self.assertIsNotNone(self.srv.refresh_pipeline_periodic)

    def test_notification_reloaded_pipeline(self):
        pipeline_cfg_file = self.setup_pipeline(['instance'])
        self.CONF.set_override("pipeline_cfg_file", pipeline_cfg_file)

        self.srv.run()
        self.addCleanup(self.srv.terminate)

        pipeline = self.srv.pipeline_manager.cfg_hash

        # Modify the collection targets
        updated_pipeline_cfg_file = self.setup_pipeline(['vcpus',
                                                         'disk.root.size'])
        # Move/rename the updated pipeline file to the original pipeline
        # file path as recorded in oslo config
        shutil.move(updated_pipeline_cfg_file, pipeline_cfg_file)
        start = time.time()
        while time.time() - start < 10:
            if pipeline != self.srv.pipeline_manager.cfg_hash:
                break
        else:
            self.fail("Pipeline failed to reload")

    def test_notification_reloaded_event_pipeline(self):
        ev_pipeline_cfg_file = self.setup_event_pipeline(
            ['compute.instance.create.start'])
        self.CONF.set_override("event_pipeline_cfg_file", ev_pipeline_cfg_file)

        self.srv.run()
        self.addCleanup(self.srv.terminate)

        pipeline = self.srv.event_pipeline_manager.cfg_hash

        # Modify the collection targets
        updated_ev_pipeline_cfg_file = self.setup_event_pipeline(
            ['compute.instance.*'])

        # Move/rename the updated pipeline file to the original pipeline
        # file path as recorded in oslo config
        shutil.move(updated_ev_pipeline_cfg_file, ev_pipeline_cfg_file)
        start = time.time()
        while time.time() - start < 10:
            if pipeline != self.srv.event_pipeline_manager.cfg_hash:
                break
        else:
            self.fail("Pipeline failed to reload")


class TestRealNotification(BaseRealNotification):

    def setUp(self):
        super(TestRealNotification, self).setUp()
        self.srv = notification.NotificationService(0, self.CONF)

    @mock.patch('ceilometer.publisher.test.TestPublisher')
    def test_notification_service(self, fake_publisher_cls):
        fake_publisher_cls.return_value = self.publisher
        self._check_notification_service()

    @mock.patch('ceilometer.publisher.test.TestPublisher')
    def test_notification_service_error_topic(self, fake_publisher_cls):
        fake_publisher_cls.return_value = self.publisher
        self.srv.run()
        self.addCleanup(self.srv.terminate)
        notifier = messaging.get_notifier(self.transport,
                                          'compute.vagrant-precise')
        notifier.error({}, 'compute.instance.error',
                       TEST_NOTICE_PAYLOAD)
        start = time.time()
        while time.time() - start < 60:
            if len(self.publisher.events) >= self.expected_events:
                break
        self.assertEqual(self.expected_events, len(self.publisher.events))


class TestRealNotificationHA(BaseRealNotification):

    def setUp(self):
        super(TestRealNotificationHA, self).setUp()
        self.CONF.set_override('workload_partitioning', True,
                               group='notification')
        self.srv = notification.NotificationService(0, self.CONF)

    @mock.patch('ceilometer.publisher.test.TestPublisher')
    def test_notification_service(self, fake_publisher_cls):
        fake_publisher_cls.return_value = self.publisher
        self._check_notification_service()

    @mock.patch.object(oslo_messaging.MessageHandlingServer, 'start')
    def test_notification_threads(self, m_listener):
        self.CONF.set_override('batch_size', 1, group='notification')
        self.srv.run()
        m_listener.assert_called_with(override_pool_size=None)
        m_listener.reset_mock()
        self.CONF.set_override('batch_size', 2, group='notification')
        self.srv.run()
        m_listener.assert_called_with(override_pool_size=1)

    @mock.patch('oslo_messaging.get_batch_notification_listener')
    def test_reset_listener_on_refresh(self, mock_listener):
        mock_listener.side_effect = [
            mock.MagicMock(),  # main listener
            mock.MagicMock(),  # pipeline listener
            mock.MagicMock(),  # refresh pipeline listener
        ]

        self.srv.run()
        self.addCleanup(self.srv.terminate)

        def _check_listener_targets():
            args, kwargs = mock_listener.call_args
            self.assertEqual(20, len(args[1]))
            self.assertIsInstance(args[1][0], oslo_messaging.Target)

        _check_listener_targets()

        listener = self.srv.pipeline_listener
        self.srv._configure_pipeline_listener()
        self.assertIsNot(listener, self.srv.pipeline_listener)

        _check_listener_targets()

    @mock.patch('oslo_messaging.get_batch_notification_listener')
    def test_retain_common_targets_on_refresh(self, mock_listener):
        with mock.patch('ceilometer.coordination.PartitionCoordinator'
                        '.extract_my_subset', return_value=[1, 2]):
            self.srv.run()
            self.addCleanup(self.srv.terminate)
        listened_before = [target.topic for target in
                           mock_listener.call_args[0][1]]
        self.assertEqual(4, len(listened_before))
        with mock.patch('ceilometer.coordination.PartitionCoordinator'
                        '.extract_my_subset', return_value=[1, 3]):
            self.srv._refresh_agent(None)
        listened_after = [target.topic for target in
                          mock_listener.call_args[0][1]]
        self.assertEqual(4, len(listened_after))
        common = set(listened_before) & set(listened_after)
        for topic in common:
            self.assertTrue(topic.endswith('1'))

    @mock.patch('oslo_messaging.get_batch_notification_listener')
    def test_notify_to_relevant_endpoint(self, mock_listener):
        self.srv.run()
        self.addCleanup(self.srv.terminate)

        targets = mock_listener.call_args[0][1]
        self.assertIsNotEmpty(targets)

        endpoints = {}
        for endpoint in mock_listener.call_args[0][2]:
            self.assertEqual(1, len(endpoint.publish_context.pipelines))
            pipe = list(endpoint.publish_context.pipelines)[0]
            endpoints[pipe.name] = endpoint

        notifiers = []
        notifiers.extend(self.srv.pipe_manager.transporters[0][2])
        notifiers.extend(self.srv.event_pipe_manager.transporters[0][2])
        for notifier in notifiers:
            filter_rule = endpoints[notifier.publisher_id].filter_rule
            self.assertEqual(True, filter_rule.match(None,
                                                     notifier.publisher_id,
                                                     None, None, None))

    @mock.patch('oslo_messaging.Notifier.sample')
    def test_broadcast_to_relevant_pipes_only(self, mock_notifier):
        self.srv.run()
        self.addCleanup(self.srv.terminate)
        for endpoint in self.srv.listeners[0].dispatcher.endpoints:
            if (hasattr(endpoint, 'filter_rule') and
                not endpoint.filter_rule.match(None, None, 'nonmatching.end',
                                               None, None)):
                continue
            endpoint.info([{
                'ctxt': TEST_NOTICE_CTXT,
                'publisher_id': 'compute.vagrant-precise',
                'event_type': 'nonmatching.end',
                'payload': TEST_NOTICE_PAYLOAD,
                'metadata': TEST_NOTICE_METADATA}])
        self.assertFalse(mock_notifier.called)
        for endpoint in self.srv.listeners[0].dispatcher.endpoints:
            if (hasattr(endpoint, 'filter_rule') and
                not endpoint.filter_rule.match(None, None,
                                               'compute.instance.create.end',
                                               None, None)):
                continue
            endpoint.info([{
                'ctxt': TEST_NOTICE_CTXT,
                'publisher_id': 'compute.vagrant-precise',
                'event_type': 'compute.instance.create.end',
                'payload': TEST_NOTICE_PAYLOAD,
                'metadata': TEST_NOTICE_METADATA}])

        self.assertTrue(mock_notifier.called)
        self.assertEqual(3, mock_notifier.call_count)
        self.assertEqual('pipeline.event',
                         mock_notifier.call_args_list[0][1]['event_type'])
        self.assertEqual('ceilometer.pipeline',
                         mock_notifier.call_args_list[1][1]['event_type'])
        self.assertEqual('ceilometer.pipeline',
                         mock_notifier.call_args_list[2][1]['event_type'])


class TestRealNotificationMultipleAgents(tests_base.BaseTestCase):
    def setup_pipeline(self, transformers):
        pipeline = yaml.dump({
            'sources': [{
                'name': 'test_pipeline',
                'interval': 5,
                'meters': ['vcpus', 'memory'],
                'sinks': ['test_sink']
            }],
            'sinks': [{
                'name': 'test_sink',
                'transformers': transformers,
                'publishers': ['test://']
            }]
        })
        if six.PY3:
            pipeline = pipeline.encode('utf-8')

        pipeline_cfg_file = fileutils.write_to_tempfile(content=pipeline,
                                                        prefix="pipeline",
                                                        suffix="yaml")
        return pipeline_cfg_file

    def setup_event_pipeline(self):
        pipeline = yaml.dump({
            'sources': [],
            'sinks': []
        })
        if six.PY3:
            pipeline = pipeline.encode('utf-8')

        pipeline_cfg_file = fileutils.write_to_tempfile(
            content=pipeline, prefix="event_pipeline", suffix="yaml")
        return pipeline_cfg_file

    def setUp(self):
        super(TestRealNotificationMultipleAgents, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.CONF([], project='ceilometer', validate_default_values=True)
        self.setup_messaging(self.CONF, 'nova')

        pipeline_cfg_file = self.setup_pipeline(['instance', 'memory'])
        event_pipeline_cfg_file = self.setup_event_pipeline()
        self.CONF.set_override("pipeline_cfg_file", pipeline_cfg_file)
        self.CONF.set_override("event_pipeline_cfg_file",
                               event_pipeline_cfg_file)
        self.CONF.set_override("backend_url", None, group="coordination")
        self.CONF.set_override("disable_non_metric_meters", False,
                               group="notification")
        self.CONF.set_override('workload_partitioning', True,
                               group='notification')
        self.CONF.set_override('pipeline_processing_queues', 2,
                               group='notification')
        self.publisher = test_publisher.TestPublisher(self.CONF, "")
        self.publisher2 = test_publisher.TestPublisher(self.CONF, "")

    def _check_notifications(self, fake_publisher_cls):
        fake_publisher_cls.side_effect = [self.publisher, self.publisher2]

        self.srv = notification.NotificationService(0, self.CONF)
        self.srv2 = notification.NotificationService(0, self.CONF)
        with mock.patch('ceilometer.coordination.PartitionCoordinator'
                        '._get_members', return_value=['harry', 'lloyd']):
            with mock.patch('uuid.uuid4', return_value='harry'):
                self.srv.run()
            self.addCleanup(self.srv.terminate)
            with mock.patch('uuid.uuid4', return_value='lloyd'):
                self.srv2.run()
            self.addCleanup(self.srv2.terminate)

        notifier = messaging.get_notifier(self.transport,
                                          "compute.vagrant-precise")
        payload1 = TEST_NOTICE_PAYLOAD.copy()
        payload1['instance_id'] = '0'
        notifier.info({}, 'compute.instance.create.end', payload1)
        payload2 = TEST_NOTICE_PAYLOAD.copy()
        payload2['instance_id'] = '1'
        notifier.info({}, 'compute.instance.create.end', payload2)
        self.expected_samples = 4
        with mock.patch('six.moves.builtins.hash', lambda x: int(x)):
            start = time.time()
            while time.time() - start < 60:
                if (len(self.publisher.samples + self.publisher2.samples) >=
                        self.expected_samples):
                    break

        self.assertEqual(2, len(self.publisher.samples))
        self.assertEqual(2, len(self.publisher2.samples))
        self.assertEqual(1, len(set(
            s.resource_id for s in self.publisher.samples)))
        self.assertEqual(1, len(set(
            s.resource_id for s in self.publisher2.samples)))

    @mock.patch('ceilometer.publisher.test.TestPublisher')
    def test_multiple_agents_no_transform(self, fake_publisher_cls):
        pipeline_cfg_file = self.setup_pipeline([])
        self.CONF.set_override("pipeline_cfg_file", pipeline_cfg_file)
        self._check_notifications(fake_publisher_cls)

    @mock.patch('ceilometer.publisher.test.TestPublisher')
    def test_multiple_agents_transform(self, fake_publisher_cls):
        pipeline_cfg_file = self.setup_pipeline(
            [{
                'name': 'unit_conversion',
                'parameters': {
                    'source': {},
                    'target': {'name': 'cpu_mins',
                               'unit': 'min',
                               'scale': 'volume'},
                }
            }])
        self.CONF.set_override("pipeline_cfg_file", pipeline_cfg_file)
        self._check_notifications(fake_publisher_cls)

    @mock.patch('ceilometer.publisher.test.TestPublisher')
    def test_multiple_agents_multiple_transform(self, fake_publisher_cls):
        pipeline_cfg_file = self.setup_pipeline(
            [{
                'name': 'unit_conversion',
                'parameters': {
                    'source': {},
                    'target': {'name': 'cpu_mins',
                               'unit': 'min',
                               'scale': 'volume'},
                }
            }, {
                'name': 'unit_conversion',
                'parameters': {
                    'source': {},
                    'target': {'name': 'cpu_mins',
                               'unit': 'min',
                               'scale': 'volume'},
                }
            }])
        self.CONF.set_override("pipeline_cfg_file", pipeline_cfg_file)
        self._check_notifications(fake_publisher_cls)
