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
"""Tests for ceilometer/publish.py
"""

import datetime

from ceilometer.openstack.common import rpc
from ceilometer.tests import base

from ceilometer import counter
from ceilometer import publish


class TestPublish(base.TestCase):

    test_data = counter.Counter(
        name='test',
        type=counter.TYPE_CUMULATIVE,
        volume=1,
        user_id='test',
        project_id='test',
        resource_id='test_run_tasks',
        timestamp=datetime.datetime.utcnow().isoformat(),
        resource_metadata={'name': 'TestPublish',
                           },
        )

    def faux_notify(self, context, topic, msg):
        self.notifications.append((topic, msg))

    def setUp(self):
        super(TestPublish, self).setUp()
        self.notifications = []
        self.stubs.Set(rpc, 'cast', self.faux_notify)
        publish.publish_counter(None,
                                self.test_data,
                                'metering',
                                'not-so-secret',
                                'test',
                                )

    def test_notify(self):
        assert len(self.notifications) == 2

    def test_notify_topics(self):
        topics = [n[0] for n in self.notifications]
        assert topics == ['metering', 'metering.test']
