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
"""Test listing raw events.
"""

import datetime
import logging

from ceilometer import counter
from ceilometer import meter

from ceilometer.tests import api as tests_api

LOG = logging.getLogger(__name__)


class TestListEvents(tests_api.TestBase):

    def setUp(self):
        super(TestListEvents, self).setUp()
        self.counter1 = counter.Counter(
            'source1',
            'instance',
            'cumulative',
            1,
            'user-id',
            'project-id',
            'resource-id',
            timestamp=datetime.datetime(2012, 7, 2, 10, 40),
            duration=0,
            resource_metadata={'display_name': 'test-server',
                               'tag': 'self.counter',
                               }
            )
        msg = meter.meter_message_from_counter(self.counter1)
        self.conn.record_metering_data(msg)

        self.counter2 = counter.Counter(
            'source2',
            'instance',
            'cumulative',
            1,
            'user-id',
            'project-id',
            'resource-id-alternate',
            timestamp=datetime.datetime(2012, 7, 2, 10, 41),
            duration=0,
            resource_metadata={'display_name': 'test-server',
                               'tag': 'self.counter2',
                               }
            )
        msg2 = meter.meter_message_from_counter(self.counter2)
        self.conn.record_metering_data(msg2)

    def test_empty(self):
        data = self.get('/users/no-such-user')
        self.assertEquals({'events': []}, data)

    def test_with_user(self):
        data = self.get('/users/user-id')
        self.assertEquals(2, len(data['events']))

    def test_with_user_and_meters(self):
        data = self.get('/users/user-id/meters/instance')
        self.assertEquals(2, len(data['events']))

    def test_with_user_and_meters_invalid(self):
        data = self.get('/users/user-id/meters/no-such-meter')
        self.assertEquals(0, len(data['events']))

    def test_with_source_and_user(self):
        data = self.get('/sources/source1/users/user-id')
        ids = [r['resource_id'] for r in data['events']]
        self.assertEquals(['resource-id'], ids)

    def test_with_resource(self):
        data = self.get('/users/user-id/resources/resource-id')
        ids = [r['resource_id'] for r in data['events']]
        self.assertEquals(['resource-id'], ids)
