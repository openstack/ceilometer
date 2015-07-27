#
# Copyright 2015 Hewlett Packard
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
from oslo_utils import timeutils
from oslotest import base

from ceilometer.database import notifications
from ceilometer import sample

NOW = timeutils.utcnow().isoformat()

TENANT_ID = u'76538754af6548f5b53cf9af2d35d582'
USER_ID = u'b70ece400e4e45c187168c40fa42ff7a'
INSTANCE_STATE = u'active'
INSTANCE_TYPE = u'm1.rd-tiny'
RESOURCE_ID = u'a8b55824-e731-40a3-a32d-de81474d74b2'
SERVICE_ID = u'2f3ff068-2bfb-4f70-9a9d-a6bb65bc084b'
NOVA_INSTANCE_ID = u'1cf6ce1b-708b-4e6a-8ecf-2b60c8ccd435'
PUBLISHER_ID = u'trove'


def _trove_notification_for(operation):
    return {
        u'event_type': '%s.instance.%s' % (notifications.SERVICE,
                                           operation),
        u'priority': u'INFO',
        u'timestamp': NOW,
        u'publisher_id': PUBLISHER_ID,
        u'message_id': u'67ba0a2a-32bd-4cdf-9bfb-ef9cefcd0f63',
        u'payload': {
            u'state_description': INSTANCE_STATE,
            u'user_id': USER_ID,
            u'audit_period_beginning': u'2015-07-10T20:05:29.870091Z',
            u'tenant_id': TENANT_ID,
            u'created_at': u'2015-06-29T20:52:12.000000',
            u'instance_type_id': u'7',
            u'launched_at': u'2015-06-29T20:52:12.000000',
            u'instance_id': RESOURCE_ID,
            u'instance_type': INSTANCE_TYPE,
            u'state': INSTANCE_STATE,
            u'service_id': SERVICE_ID,
            u'nova_instance_id': NOVA_INSTANCE_ID,
            u'display_name': u'test',
            u'instance_name': u'test',
            u'region': u'LOCAL_DEV',
            u'audit_period_ending': u'2015-07-10T21:05:29.870091Z'
        },

    }


class TestNotification(base.BaseTestCase):
    def _verify_common_sample(self, actual, operation):
        self.assertIsNotNone(actual)
        self.assertEqual('%s.instance.%s' % (notifications.SERVICE, operation),
                         actual.name)
        self.assertEqual(NOW, actual.timestamp)
        self.assertEqual(sample.TYPE_CUMULATIVE, actual.type)
        self.assertEqual(TENANT_ID, actual.project_id)
        self.assertEqual(RESOURCE_ID, actual.resource_id)
        self.assertEqual(USER_ID, actual.user_id)
        self.assertEqual(3600, actual.volume)
        self.assertEqual('s', actual.unit)

        metadata = actual.resource_metadata
        self.assertEqual(PUBLISHER_ID, metadata.get('host'))

    def _test_operation(self, operation):
        notif = _trove_notification_for(operation)
        handler = notifications.InstanceExists(mock.Mock())
        data = list(handler.process_notification(notif))
        self.assertEqual(1, len(data))
        self._verify_common_sample(data[0], operation)

    def test_exists(self):
        self._test_operation('exists')
