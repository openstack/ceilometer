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
from unittest import mock

import fixtures
import oslo_messaging
from oslo_utils import fileutils
import yaml

from ceilometer.pipeline import event as event_pipe
from ceilometer import publisher
from ceilometer.publisher import test
from ceilometer import service
from ceilometer.tests import base as tests_base


TEST_NOTICE_CTXT = {
    'auth_token': '3d8b13de1b7d499587dfc69b77dc09c2',
    'is_admin': True,
    'project_id': '7c150a59fe714e6f9263774af9688f0e',
    'quota_class': None,
    'read_deleted': 'no',
    'remote_address': '10.0.2.15',
    'request_id': 'req-d68b36e0-9233-467f-9afb-d81435d64d66',
    'roles': ['admin'],
    'timestamp': '2012-05-08T20:23:41.425105',
    'user_id': '1e3ce043029547f1a61c1996d1a531a2',
}

TEST_NOTICE_METADATA = {
    'message_id': 'dae6f69c-00e0-41c0-b371-41ec3b7f4451',
    'timestamp': '2012-05-08 20:23:48.028195',
}

TEST_NOTICE_PAYLOAD = {
    'created_at': '2012-05-08 20:23:41',
    'deleted_at': '',
    'disk_gb': 0,
    'display_name': 'testme',
    'fixed_ips': [{'address': '10.0.0.2',
                    'floating_ips': [],
                    'meta': {},
                    'type': 'fixed',
                    'version': 4}],
    'image_ref_url': 'http://10.0.2.15:9292/images/UUID',
    'instance_id': '9f9d01b9-4a58-4271-9e27-398b21ab20d1',
    'instance_type': 'm1.tiny',
    'instance_type_id': 2,
    'launched_at': '2012-05-08 20:23:47.985999',
    'memory_mb': 512,
    'state': 'active',
    'state_description': '',
    'tenant_id': '7c150a59fe714e6f9263774af9688f0e',
    'user_id': '1e3ce043029547f1a61c1996d1a531a2',
    'reservation_id': '1e3ce043029547f1a61c1996d1a531a3',
    'vcpus': 1,
    'root_gb': 0,
    'ephemeral_gb': 0,
    'host': 'compute-host-name',
    'availability_zone': '1e3ce043029547f1a61c1996d1a531a4',
    'os_type': 'linux?',
    'architecture': 'x86',
    'image_ref': 'UUID',
    'kernel_id': '1e3ce043029547f1a61c1996d1a531a5',
    'ramdisk_id': '1e3ce043029547f1a61c1996d1a531a6',
}


class TestEventEndpoint(tests_base.BaseTestCase):

    @staticmethod
    def get_publisher(conf, url, namespace=''):
        fake_drivers = {'test://': test.TestPublisher,
                        'except://': test.TestPublisher}
        return fake_drivers[url](conf, url)

    def _setup_pipeline(self, publishers):
        ev_pipeline = yaml.dump({
            'sources': [{
                'name': 'test_event',
                'events': ['test.test'],
                'sinks': ['test_sink']
            }],
            'sinks': [{
                'name': 'test_sink',
                'publishers': publishers
            }]
        })

        ev_pipeline = ev_pipeline.encode('utf-8')
        ev_pipeline_cfg_file = fileutils.write_to_tempfile(
            content=ev_pipeline, prefix="event_pipeline", suffix="yaml")
        self.CONF.set_override('event_pipeline_cfg_file',
                               ev_pipeline_cfg_file)

        ev_pipeline_mgr = event_pipe.EventPipelineManager(self.CONF)
        return ev_pipeline_mgr

    def _setup_endpoint(self, publishers):
        ev_pipeline_mgr = self._setup_pipeline(publishers)
        self.endpoint = event_pipe.EventEndpoint(
            ev_pipeline_mgr.conf, ev_pipeline_mgr.publisher())

        self.endpoint.event_converter = mock.MagicMock()
        self.endpoint.event_converter.to_event.return_value = mock.MagicMock(
            event_type='test.test')

    def setUp(self):
        super(TestEventEndpoint, self).setUp()
        self.CONF = service.prepare_service([], [])
        self.setup_messaging(self.CONF)

        self.useFixture(fixtures.MockPatchObject(
            publisher, 'get_publisher',
            side_effect=self.get_publisher))
        self.fake_publisher = mock.Mock()
        self.useFixture(fixtures.MockPatch(
            'ceilometer.publisher.test.TestPublisher',
            return_value=self.fake_publisher))

    def test_message_to_event(self):
        self._setup_endpoint(['test://'])
        self.endpoint.info([{'ctxt': TEST_NOTICE_CTXT,
                             'publisher_id': 'compute.vagrant-precise',
                             'event_type': 'compute.instance.create.end',
                             'payload': TEST_NOTICE_PAYLOAD,
                             'metadata': TEST_NOTICE_METADATA}])

    def test_bad_event_non_ack_and_requeue(self):
        self._setup_endpoint(['test://'])
        self.fake_publisher.publish_events.side_effect = Exception
        self.CONF.set_override("ack_on_event_error", False,
                               group="notification")
        ret = self.endpoint.info([{'ctxt': TEST_NOTICE_CTXT,
                                   'publisher_id': 'compute.vagrant-precise',
                                   'event_type': 'compute.instance.create.end',
                                   'payload': TEST_NOTICE_PAYLOAD,
                                   'metadata': TEST_NOTICE_METADATA}])

        self.assertEqual(oslo_messaging.NotificationResult.REQUEUE, ret)

    def test_message_to_event_bad_event(self):
        self._setup_endpoint(['test://'])
        self.fake_publisher.publish_events.side_effect = Exception
        self.CONF.set_override("ack_on_event_error", False,
                               group="notification")

        message = {
            'payload': {'event_type': "foo", 'message_id': "abc"},
            'metadata': {},
            'ctxt': {}
        }
        with mock.patch("ceilometer.pipeline.event.LOG") as mock_logger:
            ret = self.endpoint.process_notifications('info', [message])
            self.assertEqual(oslo_messaging.NotificationResult.REQUEUE, ret)
            exception_mock = mock_logger.error
            self.assertIn('Exit after error from publisher',
                          exception_mock.call_args_list[0][0][0])

    def test_message_to_event_bad_event_multi_publish(self):

        self._setup_endpoint(['test://', 'except://'])

        self.fake_publisher.publish_events.side_effect = Exception
        self.CONF.set_override("ack_on_event_error", False,
                               group="notification")

        message = {
            'payload': {'event_type': "foo", 'message_id': "abc"},
            'metadata': {},
            'ctxt': {}
        }
        with mock.patch("ceilometer.pipeline.event.LOG") as mock_logger:
            ret = self.endpoint.process_notifications('info', [message])
            self.assertEqual(oslo_messaging.NotificationResult.HANDLED, ret)
            exception_mock = mock_logger.error
            self.assertIn('Continue after error from publisher',
                          exception_mock.call_args_list[0][0][0])
