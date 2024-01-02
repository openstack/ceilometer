#
# Copyright 2024 cmss, inc.
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
"""Tests for ceilometer/publisher/opentelemetry.py"""

import datetime
import json
import time
from unittest import mock
import uuid

from oslo_utils import timeutils
from oslotest import base
import requests
from urllib import parse as urlparse

from ceilometer.publisher import opentelemetry_http
from ceilometer import sample
from ceilometer import service


class TestOpentelemetryHttpPublisher(base.BaseTestCase):

    resource_id = str(uuid.uuid4())
    format_time = datetime.datetime.utcnow().isoformat()
    sample_data = [
        sample.Sample(
            name='alpha',
            type=sample.TYPE_CUMULATIVE,
            unit='',
            volume=1,
            user_id='test',
            project_id='test',
            resource_id=resource_id,
            timestamp=format_time,
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
            timestamp=format_time,
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
            timestamp=format_time,
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
            timestamp=format_time,
            resource_metadata={'name': 'TestPublish'},
        ),
    ]

    @staticmethod
    def _make_fake_json(sample, format_time):
        struct_time = timeutils.parse_isotime(format_time).timetuple()
        unix_time = int(time.mktime(struct_time))
        if sample.type == "cumulative":
            metric_type = "counter"
        else:
            metric_type = "gauge"
        return {"resource_metrics": [{
            "scope_metrics": [{
                "scope": {
                    "name": "ceilometer",
                    "version": "v1"
                },
                "metrics": [{
                    "name": sample.name.replace(".", "_"),
                    "description": sample.name + " unit:",
                    "unit": "",
                    metric_type: {
                        "data_points": [{
                            "attributes": [{
                                "key": "resource_id",
                                "value": {
                                    "string_value": sample.resource_id
                                }
                            }, {
                                "key": "user_id",
                                "value": {
                                    "string_value": "test"
                                }
                            }, {
                                "key": "project_id",
                                "value": {
                                    "string_value": "test"
                                }
                            }],
                            "start_time_unix_nano": unix_time,
                            "time_unix_nano": unix_time,
                            "as_double": sample.volume,
                            "flags": 0
                        }]}}]}]}]}

    def setUp(self):
        super(TestOpentelemetryHttpPublisher, self).setUp()
        self.CONF = service.prepare_service([], [])

    def test_post_samples(self):
        """Test publisher post."""
        parsed_url = urlparse.urlparse(
            'opentelemetryhttp://localhost:4318/v1/metrics')
        publisher = opentelemetry_http.OpentelemetryHttpPublisher(
            self.CONF, parsed_url)

        res = requests.Response()
        res.status_code = 200
        with mock.patch.object(requests.Session, 'post',
                               return_value=res) as m_req:
            publisher.publish_samples(self.sample_data)

        datas = []
        for s in self.sample_data:
            datas.append(self._make_fake_json(s, self.format_time))
        expected = []
        for d in datas:
            expected.append(mock.call('http://localhost:4318/v1/metrics',
                                      auth=None,
                                      cert=None,
                                      data=json.dumps(d),
                                      headers={'Content-type':
                                               'application/json'},
                                      timeout=5,
                                      verify=True))
        self.assertEqual(expected, m_req.mock_calls)

    def test_post_samples_ssl(self):
        """Test publisher post."""
        parsed_url = urlparse.urlparse(
            'opentelemetryhttp://localhost:4318/v1/metrics?ssl=1')
        publisher = opentelemetry_http.OpentelemetryHttpPublisher(
            self.CONF, parsed_url)

        res = requests.Response()
        res.status_code = 200
        with mock.patch.object(requests.Session, 'post',
                               return_value=res) as m_req:
            publisher.publish_samples(self.sample_data)

        datas = []
        for s in self.sample_data:
            datas.append(self._make_fake_json(s, self.format_time))
        expected = []
        for d in datas:
            expected.append(mock.call('https://localhost:4318/v1/metrics',
                                      auth=None,
                                      cert=None,
                                      data=json.dumps(d),
                                      headers={'Content-type':
                                               'application/json'},
                                      timeout=5,
                                      verify=True))
        self.assertEqual(expected, m_req.mock_calls)
