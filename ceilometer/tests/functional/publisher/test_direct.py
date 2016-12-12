#
# Copyright 2015 Red Hat
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
"""Tests for ceilometer/publisher/direct.py
"""

import datetime
import uuid

from oslo_utils import netutils

from ceilometer.publisher import direct
from ceilometer import sample
from ceilometer.tests import db as tests_db


class TestDirectPublisher(tests_db.TestBase):

    resource_id = str(uuid.uuid4())

    test_data = [
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

    def test_direct_publisher(self):
        """Test samples are saved."""
        self.CONF.set_override('connection', self.db_manager.url,
                               group='database')
        parsed_url = netutils.urlsplit('direct://')
        publisher = direct.DirectPublisher(self.CONF, parsed_url)
        publisher.publish_samples(self.test_data)

        meters = list(self.conn.get_meters(resource=self.resource_id))
        names = sorted([meter.name for meter in meters])

        self.assertEqual(3, len(meters), 'There should be 3 samples')
        self.assertEqual(['alpha', 'beta', 'gamma'], names)
