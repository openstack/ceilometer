#
# Copyright 2013 IBM Corp
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

import datetime
import uuid

import mock
from oslotest import base
import requests

from ceilometer.dispatcher import http
from ceilometer.event.storage import models as event_models
from ceilometer.publisher import utils
from ceilometer import service


class TestDispatcherHttp(base.BaseTestCase):
    """Test sending meters with the http dispatcher"""

    def setUp(self):
        super(TestDispatcherHttp, self).setUp()
        self.CONF = service.prepare_service([], [])
        self.msg = {'counter_name': 'test',
                    'resource_id': self.id(),
                    'counter_volume': 1,
                    }
        self.msg['message_signature'] = utils.compute_signature(
            self.msg, self.CONF.publisher.telemetry_secret,
        )

    def test_http_dispatcher_config_options(self):
        self.CONF.dispatcher_http.target = 'fake'
        self.CONF.dispatcher_http.timeout = 2
        dispatcher = http.HttpDispatcher(self.CONF)

        self.assertEqual('fake', dispatcher.target)
        self.assertEqual(2, dispatcher.timeout)

    def test_http_dispatcher_with_no_target(self):
        self.CONF.dispatcher_http.target = ''
        dispatcher = http.HttpDispatcher(self.CONF)

        # The target should be None
        self.assertEqual('', dispatcher.target)

        with mock.patch.object(requests, 'post') as post:
            dispatcher.record_metering_data(self.msg)

        # Since the target is not set, no http post should occur, thus the
        # call_count should be zero.
        self.assertEqual(0, post.call_count)

    def test_http_dispatcher_with_no_metadata(self):
        self.CONF.dispatcher_http.target = 'fake'
        dispatcher = http.HttpDispatcher(self.CONF)

        with mock.patch.object(requests, 'post') as post:
            dispatcher.record_metering_data(self.msg)

        self.assertEqual(1, post.call_count)

    def test_http_dispatcher_with_ssl_default(self):
        self.CONF.dispatcher_http.target = 'https://example.com'
        self.CONF.dispatcher_http.verify_ssl = ''
        dispatcher = http.HttpDispatcher(self.CONF)

        self.assertEqual(True, dispatcher.verify_ssl)

        with mock.patch.object(requests, 'post') as post:
            dispatcher.record_metering_data(self.msg)

        self.assertEqual(True, post.call_args[1]['verify'])

    def test_http_dispatcher_with_ssl_true(self):
        self.CONF.dispatcher_http.target = 'https://example.com'
        self.CONF.dispatcher_http.verify_ssl = 'true'
        dispatcher = http.HttpDispatcher(self.CONF)

        self.assertEqual(True, dispatcher.verify_ssl)

        with mock.patch.object(requests, 'post') as post:
            dispatcher.record_metering_data(self.msg)

        self.assertEqual(True, post.call_args[1]['verify'])

    def test_http_dispatcher_with_ssl_false(self):
        self.CONF.dispatcher_http.target = 'https://example.com'
        self.CONF.dispatcher_http.verify_ssl = 'false'
        dispatcher = http.HttpDispatcher(self.CONF)

        self.assertEqual(False, dispatcher.verify_ssl)

        with mock.patch.object(requests, 'post') as post:
            dispatcher.record_metering_data(self.msg)

        self.assertEqual(False, post.call_args[1]['verify'])

    def test_http_dispatcher_with_ssl_path(self):
        self.CONF.dispatcher_http.target = 'https://example.com'
        self.CONF.dispatcher_http.verify_ssl = '/path/to/cert.crt'
        dispatcher = http.HttpDispatcher(self.CONF)

        self.assertEqual('/path/to/cert.crt', dispatcher.verify_ssl)

        with mock.patch.object(requests, 'post') as post:
            dispatcher.record_metering_data(self.msg)

        self.assertEqual('/path/to/cert.crt', post.call_args[1]['verify'])

    def test_http_dispatcher_non_batch(self):
        self.CONF.dispatcher_http.target = 'fake'
        self.CONF.dispatcher_http.batch_mode = False
        dispatcher = http.HttpDispatcher(self.CONF)

        with mock.patch('requests.post') as post:
            dispatcher.record_metering_data([self.msg, self.msg])
            self.assertEqual(2, post.call_count)

    def test_http_dispatcher_batch(self):
        self.CONF.dispatcher_http.target = 'fake'
        self.CONF.dispatcher_http.batch_mode = True
        dispatcher = http.HttpDispatcher(self.CONF)

        with mock.patch('requests.post') as post:
            dispatcher.record_metering_data([self.msg, self.msg, self.msg])
            self.assertEqual(1, post.call_count)


class TestEventDispatcherHttp(base.BaseTestCase):
    """Test sending events with the http dispatcher"""
    def setUp(self):
        super(TestEventDispatcherHttp, self).setUp()
        self.CONF = service.prepare_service([], [])

        # repr(uuid.uuid4()) is used in test event creation to avoid an
        # exception being thrown when the uuid is serialized to JSON
        event = event_models.Event(repr(uuid.uuid4()), 'test',
                                   datetime.datetime(2012, 7, 2, 13, 53, 40),
                                   [], {})
        event = utils.message_from_event(event,
                                         self.CONF.publisher.telemetry_secret)
        self.event = event

    def test_http_dispatcher(self):
        self.CONF.dispatcher_http.event_target = 'fake'
        dispatcher = http.HttpDispatcher(self.CONF)

        with mock.patch.object(requests, 'post') as post:
            dispatcher.record_events(self.event)

        self.assertEqual(1, post.call_count)

    def test_http_dispatcher_bad_server(self):
        self.CONF.dispatcher_http.event_target = 'fake'
        dispatcher = http.HttpDispatcher(self.CONF)

        with mock.patch.object(requests, 'post') as post:
            response = requests.Response()
            response.status_code = 500
            post.return_value = response
            with mock.patch('ceilometer.dispatcher.http.LOG',
                            mock.MagicMock()) as LOG:
                dispatcher.record_events(self.event)
                self.assertTrue(LOG.exception.called)

    def test_http_dispatcher_with_no_target(self):
        self.CONF.dispatcher_http.event_target = ''
        dispatcher = http.HttpDispatcher(self.CONF)

        # The target should be None
        self.assertEqual('', dispatcher.event_target)

        with mock.patch.object(requests, 'post') as post:
            dispatcher.record_events(self.event)

        # Since the target is not set, no http post should occur, thus the
        # call_count should be zero.
        self.assertEqual(0, post.call_count)

    def test_http_dispatcher_share_target(self):
        self.CONF.dispatcher_http.event_target = 'fake'
        dispatcher = http.HttpDispatcher(self.CONF)

        with mock.patch.object(requests, 'post') as post:
            dispatcher.record_events(self.event)

        self.assertEqual('fake', post.call_args[0][0])

    def test_http_dispatcher_with_ssl_path(self):
        self.CONF.dispatcher_http.event_target = 'https://example.com'
        self.CONF.dispatcher_http.verify_ssl = '/path/to/cert.crt'
        dispatcher = http.HttpDispatcher(self.CONF)

        self.assertEqual('/path/to/cert.crt', dispatcher.verify_ssl)

        with mock.patch.object(requests, 'post') as post:
            dispatcher.record_events(self.event)

        self.assertEqual('/path/to/cert.crt', post.call_args[1]['verify'])

    def test_http_dispatcher_nonbatch_event(self):
        self.CONF.dispatcher_http.event_target = 'fake'
        self.CONF.dispatcher_http.batch_mode = False
        dispatcher = http.HttpDispatcher(self.CONF)

        with mock.patch('requests.post') as post:
            dispatcher.record_events([self.event, self.event])
            self.assertEqual(2, post.call_count)

    def test_http_dispatcher_batch_event(self):
        self.CONF.dispatcher_http.event_target = 'fake'
        self.CONF.dispatcher_http.batch_mode = True
        dispatcher = http.HttpDispatcher(self.CONF)

        with mock.patch('requests.post') as post:
            dispatcher.record_events([self.event, self.event])
            self.assertEqual(1, post.call_count)
