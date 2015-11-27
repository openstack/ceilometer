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

        def process_notification(self, message):
            pass

        def get_targets(self, conf):
            pass

    def test_plugin_info(self):
        plugin = self.FakePlugin(mock.Mock())
        plugin.to_samples_and_publish = mock.Mock()
        message = {
            'ctxt': {'user_id': 'fake_user_id',
                     'project_id': 'fake_project_id'},
            'publisher_id': 'fake.publisher_id',
            'event_type': 'fake.event',
            'payload': {'foo': 'bar'},
            'metadata': {'message_id': '3577a84f-29ec-4904-9566-12c52289c2e8',
                         'timestamp': '2015-06-1909:19:35.786893'}
        }
        plugin.info([message])
        notification = {
            'priority': 'info',
            'event_type': 'fake.event',
            'timestamp': '2015-06-1909:19:35.786893',
            '_context_user_id': 'fake_user_id',
            '_context_project_id': 'fake_project_id',
            'publisher_id': 'fake.publisher_id',
            'payload': {'foo': 'bar'},
            'message_id': '3577a84f-29ec-4904-9566-12c52289c2e8'
        }
        plugin.to_samples_and_publish.assert_called_with(mock.ANY,
                                                         notification)
