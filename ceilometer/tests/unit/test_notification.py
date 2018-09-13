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

import time

import mock
from oslo_utils import fileutils
import six
import yaml

from ceilometer import messaging
from ceilometer import notification
from ceilometer.publisher import test as test_publisher
from ceilometer import service
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


class BaseNotificationTest(tests_base.BaseTestCase):
    def run_service(self, srv):
        srv.run()
        self.addCleanup(srv.terminate)


class TestNotification(BaseNotificationTest):

    def setUp(self):
        super(TestNotification, self).setUp()
        self.CONF = service.prepare_service([], [])
        self.setup_messaging(self.CONF)
        self.srv = notification.NotificationService(0, self.CONF)

    def test_targets(self):
        self.assertEqual(15, len(self.srv.get_targets()))

    def test_start_multiple_listeners(self):
        urls = ["fake://vhost1", "fake://vhost2"]
        self.CONF.set_override("messaging_urls", urls, group="notification")
        self.srv.run()
        self.addCleanup(self.srv.terminate)
        self.assertEqual(2, len(self.srv.listeners))

    @mock.patch('oslo_messaging.get_batch_notification_listener')
    def test_unique_consumers(self, mock_listener):
        self.CONF.set_override('notification_control_exchanges', ['dup'] * 2,
                               group='notification')
        self.run_service(self.srv)
        # 1 target, 1 listener
        self.assertEqual(1, len(mock_listener.call_args_list[0][0][1]))
        self.assertEqual(1, len(self.srv.listeners))

    def test_select_pipelines(self):
        self.CONF.set_override('pipelines', ['event'], group='notification')
        self.srv.run()
        self.addCleanup(self.srv.terminate)
        self.assertEqual(1, len(self.srv.managers))
        self.assertEqual(1, len(self.srv.listeners[0].dispatcher.endpoints))

    @mock.patch('ceilometer.notification.LOG')
    def test_select_pipelines_missing(self, logger):
        self.CONF.set_override('pipelines', ['meter', 'event', 'bad'],
                               group='notification')
        self.srv.run()
        self.addCleanup(self.srv.terminate)
        self.assertEqual(2, len(self.srv.managers))
        logger.error.assert_called_with(
            'Could not load the following pipelines: %s', set(['bad']))


class BaseRealNotification(BaseNotificationTest):
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
        self.CONF = service.prepare_service([], [])
        self.setup_messaging(self.CONF, 'nova')

        pipeline_cfg_file = self.setup_pipeline(['vcpus', 'memory'])
        self.CONF.set_override("pipeline_cfg_file", pipeline_cfg_file)

        self.expected_samples = 2

        ev_pipeline_cfg_file = self.setup_event_pipeline(
            ['compute.instance.*'])
        self.expected_events = 1

        self.CONF.set_override("event_pipeline_cfg_file",
                               ev_pipeline_cfg_file)

        self.publisher = test_publisher.TestPublisher(self.CONF, "")

    def _check_notification_service(self):
        self.run_service(self.srv)
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
        self.run_service(self.srv)
        notifier = messaging.get_notifier(self.transport,
                                          'compute.vagrant-precise')
        notifier.error({}, 'compute.instance.error',
                       TEST_NOTICE_PAYLOAD)
        start = time.time()
        while time.time() - start < 60:
            if len(self.publisher.events) >= self.expected_events:
                break
        self.assertEqual(self.expected_events, len(self.publisher.events))
