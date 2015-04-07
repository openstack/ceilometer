#
# Copyright 2013 eNovance <licensing@enovance.com>
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

import mock
from oslo_config import fixture as fixture_config
from oslotest import base

from ceilometer.agent import plugin_base


class NotificationBaseTestCase(base.BaseTestCase):
    def setUp(self):
        super(NotificationBaseTestCase, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf

    class FakePlugin(plugin_base.NotificationBase):
        event_types = ['compute.*']

        @staticmethod
        def get_exchange_topics(conf):
            return [plugin_base.ExchangeTopics(exchange="exchange1",
                                               topics=["t1", "t2"]),
                    plugin_base.ExchangeTopics(exchange="exchange2",
                                               topics=['t3'])]

        def process_notification(self, message):
            return message

    def test_get_targets_compat(self):
        targets = self.FakePlugin(mock.Mock()).get_targets(self.CONF)
        self.assertEqual(3, len(targets))
        self.assertEqual('t1', targets[0].topic)
        self.assertEqual('exchange1', targets[0].exchange)
        self.assertEqual('t2', targets[1].topic)
        self.assertEqual('exchange1', targets[1].exchange)
        self.assertEqual('t3', targets[2].topic)
        self.assertEqual('exchange2', targets[2].exchange)
