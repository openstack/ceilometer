# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
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

import mock

import oslo.messaging
from stevedore import extension

from ceilometer.compute.notifications import instance
from ceilometer import messaging
from ceilometer import notification
from ceilometer.openstack.common.fixture import config
from ceilometer.storage import models
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
        self.CONF = self.useFixture(config.Config()).conf
        messaging.setup('fake://')
        self.addCleanup(messaging.cleanup)
        self.CONF.set_override("connection", "log://", group='database')
        self.srv = notification.NotificationService()

    def _make_test_manager(self, plugin):
        return extension.ExtensionManager.make_test_instance(
            [
                extension.Extension('test',
                                    None,
                                    None,
                                    plugin),
            ]
        )

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    @mock.patch('ceilometer.event.converter.setup_events', mock.MagicMock())
    @mock.patch.object(oslo.messaging.MessageHandlingServer, 'start',
                       mock.MagicMock())
    def test_process_notification(self):
        # If we try to create a real RPC connection, init_host() never
        # returns. Mock it out so we can establish the service
        # configuration.
        self.CONF.set_override("store_events", False, group="notification")
        self.srv.start()
        self.srv.pipeline_manager.pipelines[0] = mock.MagicMock()
        self.srv.notification_manager = self._make_test_manager(
            instance.Instance()
        )

        self.srv.info(TEST_NOTICE_CTXT, 'compute.vagrant-precise',
                      'compute.instance.create.end',
                      TEST_NOTICE_PAYLOAD, TEST_NOTICE_METADATA)

        self.assertTrue(
            self.srv.pipeline_manager.publisher.called)

    def test_process_notification_no_events(self):
        self.CONF.set_override("store_events", False, group="notification")
        self.srv.notification_manager = mock.MagicMock()
        with mock.patch.object(self.srv,
                               '_message_to_event') as fake_msg_to_event:
            self.srv.process_notification({})
            self.assertFalse(fake_msg_to_event.called)

    def test_process_notification_with_events(self):
        self.CONF.set_override("store_events", True, group="notification")
        self.srv.notification_manager = mock.MagicMock()
        with mock.patch.object(self.srv,
                               '_message_to_event') as fake_msg_to_event:
            self.srv.process_notification({})
            self.assertTrue(fake_msg_to_event.called)

    def test_message_to_event_duplicate(self):
        self.CONF.set_override("store_events", True, group="notification")
        mock_dispatcher = mock.MagicMock()
        self.srv.event_converter = mock.MagicMock()
        self.srv.event_converter.to_event.return_value = mock.MagicMock(
            event_type='test.test')
        self.srv.dispatcher_manager = self._make_test_manager(mock_dispatcher)
        mock_dispatcher.record_events.return_value = [
            (models.Event.DUPLICATE, object())]
        message = {'event_type': "foo", 'message_id': "abc"}
        self.srv._message_to_event(message)  # Should return silently.

    def test_message_to_event_bad_event(self):
        self.CONF.set_override("store_events", True, group="notification")
        self.CONF.set_override("ack_on_event_error", False,
                               group="notification")
        mock_dispatcher = mock.MagicMock()
        self.srv.event_converter = mock.MagicMock()
        self.srv.event_converter.to_event.return_value = mock.MagicMock(
            event_type='test.test')
        self.srv.dispatcher_manager = self._make_test_manager(mock_dispatcher)
        mock_dispatcher.record_events.return_value = [
            (models.Event.UNKNOWN_PROBLEM, object())]
        message = {'event_type': "foo", 'message_id': "abc"}
        ret = self.srv._message_to_event(message)
        self.assertEqual(oslo.messaging.NotificationResult.REQUEUE, ret)
