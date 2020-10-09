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
"""Tests for ceilometer/publisher/prometheus.py"""

import datetime
from unittest import mock
import uuid

from oslotest import base
import requests
from urllib import parse as urlparse

from ceilometer.publisher import prometheus
from ceilometer import sample
from ceilometer import service


class TestPrometheusPublisher(base.BaseTestCase):

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
            type=sample.TYPE_DELTA,
            unit='',
            volume=3,
            user_id='test',
            project_id='test',
            resource_id=resource_id,
            timestamp=datetime.datetime.utcnow().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
        sample.Sample(
            name='gamma',
            type=sample.TYPE_GAUGE,
            unit='',
            volume=5,
            user_id='test',
            project_id='test',
            resource_id=resource_id,
            timestamp=datetime.datetime.now().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
        sample.Sample(
            name='delta.epsilon',
            type=sample.TYPE_GAUGE,
            unit='',
            volume=7,
            user_id='test',
            project_id='test',
            resource_id=resource_id,
            timestamp=datetime.datetime.now().isoformat(),
            resource_metadata={'name': 'TestPublish'},
        ),
    ]

    def setUp(self):
        super(TestPrometheusPublisher, self).setUp()
        self.CONF = service.prepare_service([], [])

    def test_post_samples(self):
        """Test publisher post."""
        parsed_url = urlparse.urlparse(
            'prometheus://localhost:90/metrics/job/os')
        publisher = prometheus.PrometheusPublisher(self.CONF, parsed_url)

        res = requests.Response()
        res.status_code = 200
        with mock.patch.object(requests.Session, 'post',
                               return_value=res) as m_req:
            publisher.publish_samples(self.sample_data)

        data = """# TYPE alpha counter
alpha{resource_id="%s", project_id="test"} 1
beta{resource_id="%s", project_id="test"} 3
# TYPE gamma gauge
gamma{resource_id="%s", project_id="test"} 5
# TYPE delta_epsilon gauge
delta_epsilon{resource_id="%s", project_id="test"} 7
""" % (self.resource_id, self.resource_id, self.resource_id, self.resource_id)

        expected = [
            mock.call('http://localhost:90/metrics/job/os',
                      auth=None,
                      cert=None,
                      data=data,
                      headers={'Content-type': 'plain/text'},
                      timeout=5,
                      verify=True)
        ]
        self.assertEqual(expected, m_req.mock_calls)

    def test_post_samples_ssl(self):
        """Test publisher post."""
        parsed_url = urlparse.urlparse(
            'prometheus://localhost:90/metrics/job/os?ssl=1')
        publisher = prometheus.PrometheusPublisher(self.CONF, parsed_url)

        res = requests.Response()
        res.status_code = 200
        with mock.patch.object(requests.Session, 'post',
                               return_value=res) as m_req:
            publisher.publish_samples(self.sample_data)

        data = """# TYPE alpha counter
alpha{resource_id="%s", project_id="test"} 1
beta{resource_id="%s", project_id="test"} 3
# TYPE gamma gauge
gamma{resource_id="%s", project_id="test"} 5
# TYPE delta_epsilon gauge
delta_epsilon{resource_id="%s", project_id="test"} 7
""" % (self.resource_id, self.resource_id, self.resource_id, self.resource_id)

        expected = [
            mock.call('https://localhost:90/metrics/job/os',
                      auth=None,
                      cert=None,
                      data=data,
                      headers={'Content-type': 'plain/text'},
                      timeout=5,
                      verify=True)
        ]
        self.assertEqual(expected, m_req.mock_calls)
