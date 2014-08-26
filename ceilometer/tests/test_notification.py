#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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
"""Tests for Ceilometer notify daemon."""

import eventlet
import mock
from oslo.config import fixture as fixture_config
import oslo.messaging
import oslo.messaging.conffixture
from oslo.utils import timeutils
from stevedore import extension
import yaml

from ceilometer.compute.notifications import instance
from ceilometer import messaging
from ceilometer import notification
from ceilometer.openstack.common import context
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
    @mock.patch.object(oslo.messaging.MessageHandlingServer, 'start',
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

    def test_process_notification_with_events(self):
        self.CONF.set_override("store_events", True, group="notification")
        self._do_process_notification_manager_start()
        self.assertEqual(2, len(self.srv.listeners[0].dispatcher.endpoints))
        self.assertEqual(self.fake_event_endpoint,
                         self.srv.listeners[0].dispatcher.endpoints[0])

    @mock.patch('ceilometer.event.converter.get_config_file',
                mock.MagicMock(return_value=None))
    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    @mock.patch.object(oslo.messaging.MessageHandlingServer, 'start',
                       mock.MagicMock())
    def test_event_dispatcher_loaded(self):
        self.CONF.set_override("store_events", True, group="notification")
        with mock.patch.object(self.srv,
                               '_get_notifications_manager') as get_nm:
            get_nm.side_effect = self.fake_get_notifications_manager
            self.srv.start()
        self.assertEqual(2, len(self.srv.listeners[0].dispatcher.endpoints))
        event_endpoint = self.srv.listeners[0].dispatcher.endpoints[0]
        self.assertEqual(1, len(list(event_endpoint.dispatcher_manager)))


class TestRealNotification(tests_base.BaseTestCase):
    def setUp(self):
        super(TestRealNotification, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf
        self.setup_messaging(self.CONF, 'nova')

        pipeline = yaml.dump([{
            'name': 'test_pipeline',
            'interval': 5,
            'counters': ['instance', 'memory'],
            'transformers': [],
            'publishers': ['test://'],
        }])

        self.expected_samples = 2

        pipeline_cfg_file = fileutils.write_to_tempfile(content=pipeline,
                                                        prefix="pipeline",
                                                        suffix="yaml")
        self.CONF.set_override("pipeline_cfg_file", pipeline_cfg_file)
        self.srv = notification.NotificationService()
        self.publisher = test_publisher.TestPublisher("")

    @mock.patch('ceilometer.publisher.test.TestPublisher')
    def test_notification_service(self, fake_publisher_cls):
        fake_publisher_cls.return_value = self.publisher
        self.srv.start()

        notifier = messaging.get_notifier(self.transport,
                                          "compute.vagrant-precise")
        notifier.info(context.RequestContext(), 'compute.instance.create.end',
                      TEST_NOTICE_PAYLOAD)
        start = timeutils.utcnow()
        while timeutils.delta_seconds(start, timeutils.utcnow()) < 600:
            if len(self.publisher.samples) >= self.expected_samples:
                break
            eventlet.sleep(0)

        self.srv.stop()

        resources = list(set(s.resource_id for s in self.publisher.samples))
        self.assertEqual(self.expected_samples, len(self.publisher.samples))
        self.assertEqual(["9f9d01b9-4a58-4271-9e27-398b21ab20d1"], resources)
