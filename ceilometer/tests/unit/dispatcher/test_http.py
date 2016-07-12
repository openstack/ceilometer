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
from oslo_config import fixture as fixture_config
from oslotest import base
import requests

from ceilometer.dispatcher import http
from ceilometer.event.storage import models as event_models
from ceilometer.publisher import utils


class TestDispatcherHttp(base.BaseTestCase):

    def setUp(self):
        super(TestDispatcherHttp, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf
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


class TestEventDispatcherHttp(base.BaseTestCase):

    def setUp(self):
        super(TestEventDispatcherHttp, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf

    def test_http_dispatcher(self):
        self.CONF.dispatcher_http.event_target = 'fake'
        dispatcher = http.HttpDispatcher(self.CONF)

        event = event_models.Event(uuid.uuid4(), 'test',
                                   datetime.datetime(2012, 7, 2, 13, 53, 40),
                                   [], {})
        event = utils.message_from_event(event,
                                         self.CONF.publisher.telemetry_secret)

        with mock.patch.object(requests, 'post') as post:
            dispatcher.record_events(event)

        self.assertEqual(1, post.call_count)

    def test_http_dispatcher_bad(self):
        self.CONF.dispatcher_http.event_target = ''
        dispatcher = http.HttpDispatcher(self.CONF)

        event = event_models.Event(uuid.uuid4(), 'test',
                                   datetime.datetime(2012, 7, 2, 13, 53, 40),
                                   [], {})
        event = utils.message_from_event(event,
                                         self.CONF.publisher.telemetry_secret)
        with mock.patch('ceilometer.dispatcher.http.LOG',
                        mock.MagicMock()) as LOG:
            dispatcher.record_events(event)
            self.assertTrue(LOG.exception.called)

    def test_http_dispatcher_share_target(self):
        self.CONF.dispatcher_http.target = 'fake'
        dispatcher = http.HttpDispatcher(self.CONF)

        event = event_models.Event(uuid.uuid4(), 'test',
                                   datetime.datetime(2012, 7, 2, 13, 53, 40),
                                   [], {})
        event = utils.message_from_event(event,
                                         self.CONF.publisher.telemetry_secret)
        with mock.patch.object(requests, 'post') as post:
            dispatcher.record_events(event)

        self.assertEqual('fake', post.call_args[0][0])
