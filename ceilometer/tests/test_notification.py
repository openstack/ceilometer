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

import eventlet
import mock
from oslo_config import fixture as fixture_config
from oslo_context import context
import oslo_messaging
import oslo_messaging.conffixture
import oslo_service.service
from oslo_utils import timeutils
import six
from stevedore import extension
import yaml

from ceilometer.compute.notifications import instance
from ceilometer import messaging
from ceilometer import notification
from ceilometer.openstack.common import fileutils
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


class TestNotification(tests_base.BaseTestCase):

    def setUp(self):
        super(TestNotification, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.CONF.set_override("connection", "log://", group='database')
        self.CONF.set_override("store_events", False, group="notification")
        self.CONF.set_override("disable_non_metric_meters", False,
                               group="notification")
        self.setup_messaging(self.CONF)
        self.srv = notification.NotificationService()

    def fake_get_notifications_manager(self, pm):
        self.plugin = instance.Instance(pm)
        return extension.ExtensionManager.make_test_instance(
            [
                extension.Extension('test',
                                    None,
                                    None,
                                    self.plugin)
            ]
        )

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    @mock.patch.object(oslo_messaging.MessageHandlingServer, 'start',
                       mock.MagicMock())
    @mock.patch('ceilometer.event.endpoint.EventsNotificationEndpoint')
    def _do_process_notification_manager_start(self,
                                               fake_event_endpoint_class):
        with mock.patch.object(self.srv,
                               '_get_notifications_manager') as get_nm:
            get_nm.side_effect = self.fake_get_notifications_manager
            self.srv.start()
        self.fake_event_endpoint = fake_event_endpoint_class.return_value

    def test_start_multiple_listeners(self):
        urls = ["fake://vhost1", "fake://vhost2"]
        self.CONF.set_override("messaging_urls", urls, group="notification")
        self._do_process_notification_manager_start()
        self.assertEqual(2, len(self.srv.listeners))

    def test_process_notification(self):
        self._do_process_notification_manager_start()
        self.srv.pipeline_manager.pipelines[0] = mock.MagicMock()

        self.plugin.info(TEST_NOTICE_CTXT, 'compute.vagrant-precise',
                         'compute.instance.create.end',
                         TEST_NOTICE_PAYLOAD, TEST_NOTICE_METADATA)

        self.assertEqual(1, len(self.srv.listeners[0].dispatcher.endpoints))
        self.assertTrue(self.srv.pipeline_manager.publisher.called)

    def test_process_notification_no_events(self):
        self._do_process_notification_manager_start()
        self.assertEqual(1, len(self.srv.listeners[0].dispatcher.endpoints))
        self.assertNotEqual(self.fake_event_endpoint,
                            self.srv.listeners[0].dispatcher.endpoints[0])

    @mock.patch('ceilometer.pipeline.setup_event_pipeline', mock.MagicMock())
    def test_process_notification_with_events(self):
        self.CONF.set_override("store_events", True, group="notification")
        self._do_process_notification_manager_start()
        self.assertEqual(2, len(self.srv.listeners[0].dispatcher.endpoints))
        self.assertEqual(self.fake_event_endpoint,
                         self.srv.listeners[0].dispatcher.endpoints[0])

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    @mock.patch.object(oslo_messaging.MessageHandlingServer, 'start',
                       mock.MagicMock())
    @mock.patch('ceilometer.event.endpoint.EventsNotificationEndpoint')
    def test_unique_consumers(self, fake_event_endpoint_class):

        def fake_get_notifications_manager_dup_targets(pm):
            plugin = instance.Instance(pm)
            return extension.ExtensionManager.make_test_instance(
                [extension.Extension('test', None, None, plugin),
                 extension.Extension('test', None, None, plugin)])

        with mock.patch.object(self.srv,
                               '_get_notifications_manager') as get_nm:
            get_nm.side_effect = fake_get_notifications_manager_dup_targets
            self.srv.start()
            self.assertEqual(1, len(self.srv.listeners[0].dispatcher.targets))


class BaseRealNotification(tests_base.BaseTestCase):
    def setUp(self):
        super(BaseRealNotification, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.setup_messaging(self.CONF, 'nova')

        pipeline = yaml.dump([{
            'name': 'test_pipeline',
            'interval': 5,
            'counters': ['instance', 'memory'],
            'transformers': [],
            'publishers': ['test://'],
        }])
        if six.PY3:
            pipeline = pipeline.encode('utf-8')
        self.expected_samples = 2
        pipeline_cfg_file = fileutils.write_to_tempfile(content=pipeline,
                                                        prefix="pipeline",
                                                        suffix="yaml")
        self.CONF.set_override("pipeline_cfg_file", pipeline_cfg_file)

        self.CONF.set_override("store_events", True, group="notification")
        self.CONF.set_override("disable_non_metric_meters", False,
                               group="notification")
        ev_pipeline = yaml.dump({
            'sources': [{
                'name': 'test_event',
                'events': ['compute.instance.*'],
                'sinks': ['test_sink']
            }],
            'sinks': [{
                'name': 'test_sink',
                'publishers': ['test://']
            }]
        })
        if six.PY3:
            ev_pipeline = ev_pipeline.encode('utf-8')
        self.expected_events = 1
        ev_pipeline_cfg_file = fileutils.write_to_tempfile(
            content=ev_pipeline, prefix="event_pipeline", suffix="yaml")
        self.CONF.set_override("event_pipeline_cfg_file", ev_pipeline_cfg_file)
        self.CONF.set_override(
            "definitions_cfg_file",
            self.path_get('etc/ceilometer/event_definitions.yaml'),
            group='event')
        self.publisher = test_publisher.TestPublisher("")

    def _check_notification_service(self):
        self.srv.start()

        notifier = messaging.get_notifier(self.transport,
                                          "compute.vagrant-precise")
        notifier.info(context.RequestContext(), 'compute.instance.create.end',
                      TEST_NOTICE_PAYLOAD)
        start = timeutils.utcnow()
        while timeutils.delta_seconds(start, timeutils.utcnow()) < 600:
            if (len(self.publisher.samples) >= self.expected_samples and
                    len(self.publisher.events) >= self.expected_events):
                break
            eventlet.sleep(0)
        self.assertNotEqual(self.srv.listeners, self.srv.pipeline_listeners)
        self.srv.stop()

        resources = list(set(s.resource_id for s in self.publisher.samples))
        self.assertEqual(self.expected_samples, len(self.publisher.samples))
        self.assertEqual(self.expected_events, len(self.publisher.events))
        self.assertEqual(["9f9d01b9-4a58-4271-9e27-398b21ab20d1"], resources)


class TestRealNotification(BaseRealNotification):

    def setUp(self):
        super(TestRealNotification, self).setUp()
        self.srv = notification.NotificationService()

    @mock.patch('ceilometer.publisher.test.TestPublisher')
    def test_notification_service(self, fake_publisher_cls):
        fake_publisher_cls.return_value = self.publisher
        self._check_notification_service()

    @mock.patch('ceilometer.publisher.test.TestPublisher')
    def test_notification_service_error_topic(self, fake_publisher_cls):
        fake_publisher_cls.return_value = self.publisher
        self.srv.start()
        notifier = messaging.get_notifier(self.transport,
                                          'compute.vagrant-precise')
        notifier.error(context.RequestContext(), 'compute.instance.error',
                       TEST_NOTICE_PAYLOAD)
        start = timeutils.utcnow()
        while timeutils.delta_seconds(start, timeutils.utcnow()) < 600:
            if len(self.publisher.events) >= self.expected_events:
                break
            eventlet.sleep(0)
        self.srv.stop()
        self.assertEqual(self.expected_events, len(self.publisher.events))

    @mock.patch('ceilometer.publisher.test.TestPublisher')
    def test_notification_disable_non_metrics(self, fake_publisher_cls):
        self.CONF.set_override("disable_non_metric_meters", True,
                               group="notification")
        # instance is a not a metric. we should only get back memory
        self.expected_samples = 1
        fake_publisher_cls.return_value = self.publisher
        self._check_notification_service()
        self.assertEqual('memory', self.publisher.samples[0].name)

    @mock.patch('ceilometer.coordination.PartitionCoordinator')
    @mock.patch('ceilometer.publisher.test.TestPublisher')
    def test_ha_configured_agent_coord_disabled(self, fake_publisher_cls,
                                                fake_coord):
        fake_publisher_cls.return_value = self.publisher
        fake_coord1 = mock.MagicMock()
        fake_coord1.extract_my_subset.side_effect = lambda x, y: y
        fake_coord.return_value = fake_coord1
        self._check_notification_service()

    @mock.patch.object(oslo_service.service.Service, 'stop')
    def test_notification_service_start_abnormal(self, mocked):
        try:
            self.srv.stop()
        except Exception:
            pass
        self.assertEqual(1, mocked.call_count)


class TestRealNotificationHA(BaseRealNotification):

    def setUp(self):
        super(TestRealNotificationHA, self).setUp()
        self.CONF.set_override('workload_partitioning', True,
                               group='notification')
        self.srv = notification.NotificationService()

    @mock.patch('ceilometer.coordination.PartitionCoordinator')
    @mock.patch('ceilometer.publisher.test.TestPublisher')
    def test_notification_service(self, fake_publisher_cls, fake_coord):
        fake_publisher_cls.return_value = self.publisher
        fake_coord1 = mock.MagicMock()
        fake_coord1.extract_my_subset.side_effect = lambda x, y: y
        fake_coord.return_value = fake_coord1
        self._check_notification_service()

    @mock.patch('hmac.new')
    @mock.patch('ceilometer.coordination.PartitionCoordinator')
    @mock.patch('ceilometer.publisher.test.TestPublisher')
    def test_notification_service_no_secret(self, fake_publisher_cls,
                                            fake_coord, fake_hmac):
        self.CONF.set_override('telemetry_secret', None, group='publisher')
        fake_publisher_cls.return_value = self.publisher
        fake_coord1 = mock.MagicMock()
        fake_coord1.extract_my_subset.side_effect = lambda x, y: y
        fake_coord.return_value = fake_coord1
        self._check_notification_service()
        self.assertFalse(fake_hmac.called)

    def test_reset_listeners_on_refresh(self):
        self.srv.start()
        self.assertEqual(2, len(self.srv.pipeline_listeners))
        self.srv._refresh_agent(None)
        self.assertEqual(2, len(self.srv.pipeline_listeners))
        self.srv.stop()

    @mock.patch('oslo_messaging.Notifier.sample')
    def test_broadcast_to_relevant_pipes_only(self, mock_notifier):
        self.srv.start()
        for endpoint in self.srv.listeners[0].dispatcher.endpoints:
            if (hasattr(endpoint, 'filter_rule') and
                not endpoint.filter_rule.match(None, None, 'nonmatching.end',
                                               None, None)):
                continue
            endpoint.info(TEST_NOTICE_CTXT, 'compute.vagrant-precise',
                          'nonmatching.end',
                          TEST_NOTICE_PAYLOAD, TEST_NOTICE_METADATA)
        self.assertFalse(mock_notifier.called)
        for endpoint in self.srv.listeners[0].dispatcher.endpoints:
            if (hasattr(endpoint, 'filter_rule') and
                not endpoint.filter_rule.match(None, None,
                                               'compute.instance.create.end',
                                               None, None)):
                continue
            endpoint.info(TEST_NOTICE_CTXT, 'compute.vagrant-precise',
                          'compute.instance.create.end',
                          TEST_NOTICE_PAYLOAD, TEST_NOTICE_METADATA)
        self.assertTrue(mock_notifier.called)
        self.assertEqual(3, mock_notifier.call_count)
        self.assertEqual('pipeline.event',
                         mock_notifier.call_args_list[0][1]['event_type'])
        self.assertEqual('ceilometer.pipeline',
                         mock_notifier.call_args_list[1][1]['event_type'])
        self.assertEqual('ceilometer.pipeline',
                         mock_notifier.call_args_list[2][1]['event_type'])
        self.srv.stop()
