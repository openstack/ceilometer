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
from requests import Session
from six.moves.urllib import parse as urlparse
import uuid

from ceilometer.event.storage import models as event
from ceilometer.publisher import http
from ceilometer import sample


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
        traits=[], raw={'payload': {'some': 'aa'}}) for i in range(0, 2)]

    empty_event_data = [event.Event(
        message_id=str(uuid.uuid4()), event_type='event_%d' % i,
        generated=datetime.datetime.utcnow().isoformat(),
        traits=[], raw={'payload': {}}) for i in range(0, 2)]

    def test_http_publisher_config(self):
        """Test publisher config parameters."""
        # invalid hostname, the given url, results in an empty hostname
        parsed_url = urlparse.urlparse('http:/aaa.bb/path')
        self.assertRaises(ValueError, http.HttpPublisher,
                          parsed_url)

        # invalid port
        parsed_url = urlparse.urlparse('http://aaa:bb/path')
        self.assertRaises(ValueError, http.HttpPublisher,
                          parsed_url)

        parsed_url = urlparse.urlparse('http://localhost:90/path1')
        publisher = http.HttpPublisher(parsed_url)
        # By default, timeout and retry_count should be set to 1000 and 2
        # respectively
        self.assertEqual(1, publisher.timeout)
        self.assertEqual(2, publisher.max_retries)

        parsed_url = urlparse.urlparse('http://localhost:90/path1?'
                                       'timeout=19&max_retries=4')
        publisher = http.HttpPublisher(parsed_url)
        self.assertEqual(19, publisher.timeout)
        self.assertEqual(4, publisher.max_retries)

        parsed_url = urlparse.urlparse('http://localhost:90/path1?'
                                       'timeout=19')
        publisher = http.HttpPublisher(parsed_url)
        self.assertEqual(19, publisher.timeout)
        self.assertEqual(2, publisher.max_retries)

        parsed_url = urlparse.urlparse('http://localhost:90/path1?'
                                       'max_retries=6')
        publisher = http.HttpPublisher(parsed_url)
        self.assertEqual(1, publisher.timeout)
        self.assertEqual(6, publisher.max_retries)

    @mock.patch('ceilometer.publisher.http.LOG')
    def test_http_post_samples(self, thelog):
        """Test publisher post."""
        parsed_url = urlparse.urlparse('http://localhost:90/path1')
        publisher = http.HttpPublisher(parsed_url)

        res = mock.Mock()
        res.status_code = 200
        with mock.patch.object(Session, 'post', return_value=res) as m_req:
            publisher.publish_samples(None, self.sample_data)

        self.assertEqual(1, m_req.call_count)
        self.assertFalse(thelog.error.called)

        res.status_code = 401
        with mock.patch.object(Session, 'post', return_value=res) as m_req:
            publisher.publish_samples(None, self.sample_data)

        self.assertEqual(1, m_req.call_count)
        self.assertTrue(thelog.error.called)

    @mock.patch('ceilometer.publisher.http.LOG')
    def test_http_post_events(self, thelog):
        """Test publisher post."""
        parsed_url = urlparse.urlparse('http://localhost:90/path1')
        publisher = http.HttpPublisher(parsed_url)

        res = mock.Mock()
        res.status_code = 200
        with mock.patch.object(Session, 'post', return_value=res) as m_req:
            publisher.publish_events(None, self.event_data)

        self.assertEqual(1, m_req.call_count)
        self.assertFalse(thelog.error.called)

        res.status_code = 401
        with mock.patch.object(Session, 'post', return_value=res) as m_req:
            publisher.publish_samples(None, self.event_data)

        self.assertEqual(1, m_req.call_count)
        self.assertTrue(thelog.error.called)

    @mock.patch('ceilometer.publisher.http.LOG')
    def test_http_post_empty_data(self, thelog):
        parsed_url = urlparse.urlparse('http://localhost:90/path1')
        publisher = http.HttpPublisher(parsed_url)

        res = mock.Mock()
        res.status_code = 200
        with mock.patch.object(Session, 'post', return_value=res) as m_req:
            publisher.publish_events(None, self.empty_event_data)

        self.assertEqual(0, m_req.call_count)
        self.assertTrue(thelog.debug.called)
