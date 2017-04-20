#
# Copyright 2016 IBM
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
"""Tests for ceilometer/publisher/http.py
"""

import datetime
import mock
from oslotest import base
import requests
from six.moves.urllib import parse as urlparse
import uuid

from ceilometer.event.storage import models as event
from ceilometer.publisher import http
from ceilometer import sample
from ceilometer import service


class TestHttpPublisher(base.BaseTestCase):

    resource_id = str(uuid.uuid4())

    sample_data = [
        sample.Sample(
            name='alpha',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id=resource_id,
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
        sample.Sample(
            name='beta',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id=resource_id,
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
        sample.Sample(
            name='gamma',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id=resource_id,
            timestamp=datetime.datetime.now().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
    ]

    event_data = [event.Event(
        message_id=str(uuid.uuid4()), event_type='event_%d' % i,
        generated=datetime.datetime.utcnow().isoformat(),
        traits=[], raw={'payload': {'some': 'aa'}}) for i in range(3)]

    def setUp(self):
        super(TestHttpPublisher, self).setUp()
        self.CONF = service.prepare_service([], [])

    def test_http_publisher_config(self):
        """Test publisher config parameters."""
        # invalid hostname, the given url, results in an empty hostname
        parsed_url = urlparse.urlparse('http:/aaa.bb/path')
        self.assertRaises(ValueError, http.HttpPublisher,
                          self.CONF, parsed_url)

        # invalid port
        parsed_url = urlparse.urlparse('http://aaa:bb/path')
        self.assertRaises(ValueError, http.HttpPublisher,
                          self.CONF, parsed_url)

        parsed_url = urlparse.urlparse('http://localhost:90/path1')
        publisher = http.HttpPublisher(self.CONF, parsed_url)
        # By default, timeout and retry_count should be set to 5 and 2
        # respectively
        self.assertEqual(5, publisher.timeout)
        self.assertEqual(2, publisher.max_retries)

        parsed_url = urlparse.urlparse('http://localhost:90/path1?'
                                       'timeout=19&max_retries=4')
        publisher = http.HttpPublisher(self.CONF, parsed_url)
        self.assertEqual(19, publisher.timeout)
        self.assertEqual(4, publisher.max_retries)

        parsed_url = urlparse.urlparse('http://localhost:90/path1?'
                                       'timeout=19')
        publisher = http.HttpPublisher(self.CONF, parsed_url)
        self.assertEqual(19, publisher.timeout)
        self.assertEqual(2, publisher.max_retries)

        parsed_url = urlparse.urlparse('http://localhost:90/path1?'
                                       'max_retries=6')
        publisher = http.HttpPublisher(self.CONF, parsed_url)
        self.assertEqual(5, publisher.timeout)
        self.assertEqual(6, publisher.max_retries)

    @mock.patch('ceilometer.publisher.http.LOG')
    def test_http_post_samples(self, thelog):
        """Test publisher post."""
        parsed_url = urlparse.urlparse('http://localhost:90/path1')
        publisher = http.HttpPublisher(self.CONF, parsed_url)

        res = requests.Response()
        res.status_code = 200
        with mock.patch.object(requests.Session, 'post',
                               return_value=res) as m_req:
            publisher.publish_samples(self.sample_data)

        self.assertEqual(1, m_req.call_count)
        self.assertFalse(thelog.exception.called)

        res = requests.Response()
        res.status_code = 401
        with mock.patch.object(requests.Session, 'post',
                               return_value=res) as m_req:
            publisher.publish_samples(self.sample_data)

        self.assertEqual(1, m_req.call_count)
        self.assertTrue(thelog.exception.called)

    @mock.patch('ceilometer.publisher.http.LOG')
    def test_http_post_events(self, thelog):
        """Test publisher post."""
        parsed_url = urlparse.urlparse('http://localhost:90/path1')
        publisher = http.HttpPublisher(self.CONF, parsed_url)

        res = requests.Response()
        res.status_code = 200
        with mock.patch.object(requests.Session, 'post',
                               return_value=res) as m_req:
            publisher.publish_events(self.event_data)

        self.assertEqual(1, m_req.call_count)
        self.assertFalse(thelog.exception.called)

        res = requests.Response()
        res.status_code = 401
        with mock.patch.object(requests.Session, 'post',
                               return_value=res) as m_req:
            publisher.publish_events(self.event_data)

        self.assertEqual(1, m_req.call_count)
        self.assertTrue(thelog.exception.called)

    @mock.patch('ceilometer.publisher.http.LOG')
    def test_http_post_empty_data(self, thelog):
        parsed_url = urlparse.urlparse('http://localhost:90/path1')
        publisher = http.HttpPublisher(self.CONF, parsed_url)

        res = requests.Response()
        res.status_code = 200
        with mock.patch.object(requests.Session, 'post',
                               return_value=res) as m_req:
            publisher.publish_events([])

        self.assertEqual(0, m_req.call_count)
        self.assertTrue(thelog.debug.called)

    def _post_batch_control_test(self, method, data, batch):
        parsed_url = urlparse.urlparse('http://localhost:90/path1?'
                                       'batch=%s' % batch)
        publisher = http.HttpPublisher(self.CONF, parsed_url)

        with mock.patch.object(requests.Session, 'post') as post:
            getattr(publisher, method)(data)
            self.assertEqual(1 if batch else 3, post.call_count)

    def test_post_batch_sample(self):
        self._post_batch_control_test('publish_samples', self.sample_data, 1)

    def test_post_no_batch_sample(self):
        self._post_batch_control_test('publish_samples', self.sample_data, 0)

    def test_post_batch_event(self):
        self._post_batch_control_test('publish_events', self.event_data, 1)

    def test_post_no_batch_event(self):
        self._post_batch_control_test('publish_events', self.event_data, 0)

    def test_post_verify_ssl_default(self):
        parsed_url = urlparse.urlparse('http://localhost:90/path1')
        publisher = http.HttpPublisher(self.CONF, parsed_url)

        with mock.patch.object(requests.Session, 'post') as post:
            publisher.publish_samples(self.sample_data)
            self.assertTrue(post.call_args[1]['verify'])

    def test_post_verify_ssl_True(self):
        parsed_url = urlparse.urlparse('http://localhost:90/path1?'
                                       'verify_ssl=True')
        publisher = http.HttpPublisher(self.CONF, parsed_url)

        with mock.patch.object(requests.Session, 'post') as post:
            publisher.publish_samples(self.sample_data)
            self.assertTrue(post.call_args[1]['verify'])

    def test_post_verify_ssl_False(self):
        parsed_url = urlparse.urlparse('http://localhost:90/path1?'
                                       'verify_ssl=False')
        publisher = http.HttpPublisher(self.CONF, parsed_url)

        with mock.patch.object(requests.Session, 'post') as post:
            publisher.publish_samples(self.sample_data)
            self.assertFalse(post.call_args[1]['verify'])

    def test_post_verify_ssl_path(self):
        parsed_url = urlparse.urlparse('http://localhost:90/path1?'
                                       'verify_ssl=/path/to/cert.crt')
        publisher = http.HttpPublisher(self.CONF, parsed_url)

        with mock.patch.object(requests.Session, 'post') as post:
            publisher.publish_samples(self.sample_data)
            self.assertEqual('/path/to/cert.crt', post.call_args[1]['verify'])

    def test_post_basic_auth(self):
        parsed_url = urlparse.urlparse(
            'http://alice:l00kingGla$$@localhost:90/path1?')
        publisher = http.HttpPublisher(self.CONF, parsed_url)

        with mock.patch.object(requests.Session, 'post') as post:
            publisher.publish_samples(self.sample_data)
            self.assertEqual(('alice', 'l00kingGla$$'),
                             post.call_args[1]['auth'])

    def test_post_client_cert_auth(self):
        parsed_url = urlparse.urlparse('http://localhost:90/path1?'
                                       'clientcert=/path/to/cert.crt&'
                                       'clientkey=/path/to/cert.key')
        publisher = http.HttpPublisher(self.CONF, parsed_url)

        with mock.patch.object(requests.Session, 'post') as post:
            publisher.publish_samples(self.sample_data)
            self.assertEqual(('/path/to/cert.crt', '/path/to/cert.key'),
                             post.call_args[1]['cert'])

    def test_post_raw_only(self):
        parsed_url = urlparse.urlparse('http://localhost:90/path1?raw_only=1')
        publisher = http.HttpPublisher(self.CONF, parsed_url)

        with mock.patch.object(requests.Session, 'post') as post:
            publisher.publish_events(self.event_data)
            self.assertEqual(
                '[{"some": "aa"}, {"some": "aa"}, {"some": "aa"}]',
                post.call_args[1]['data'])
