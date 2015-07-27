#
# Copyright (c) 2015 Hewlett Packard Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import mock
from oslo_utils import timeutils
from oslotest import base

from ceilometer.dns import notifications
from ceilometer import sample

NOW = timeutils.utcnow().isoformat()

TENANT_ID = u'76538754af6548f5b53cf9af2d35d582'
USER_ID = u'b70ece400e4e45c187168c40fa42ff7a'
DOMAIN_STATUS = u'ACTIVE'
RESOURCE_ID = u'a8b55824-e731-40a3-a32d-de81474d74b2'
PUBLISHER_ID = u'central.ubuntu'
POOL_ID = u'794ccc2c-d751-44fe-b57f-8894c9f5c842'


def _dns_notification_for(operation):

    return {
        u'event_type': '%s.domain.%s' % (notifications.SERVICE,
                                         operation),
        u'_context_roles': [u'admin'],
        u'timestamp': NOW,
        u'_context_tenant': TENANT_ID,
        u'payload': {
            u'status': DOMAIN_STATUS,
            u'retry': 600,
            u'description': None,
            u'expire': 86400,
            u'deleted': u'0',
            u'tenant_id': TENANT_ID,
            u'created_at': u'2015-07-10T20:05:29.870091Z',
            u'updated_at': None,
            u'refresh': 3600,
            u'pool_id': POOL_ID,
            u'email': u'admin@hpcloud.com',
            u'minimum': 3600,
            u'parent_domain_id': None,
            u'version': 1,
            u'ttl': 3600,
            u'action': operation.upper(),
            u'serial': 1426295326,
            u'deleted_at': None,
            u'id': RESOURCE_ID,
            u'name': u'paas.hpcloud.com.',
            u'audit_period_beginning': u'2015-07-10T20:05:29.870091Z',
            u'audit_period_ending': u'2015-07-10T21:05:29.870091Z'
        },
        u'_context_user': USER_ID,
        u'_context_auth_token': u'b95d4fc3bb2e4a5487cad06af65ffcfc',
        u'_context_tenant': TENANT_ID,
        u'priority': u'INFO',
        u'_context_is_admin': False,
        u'publisher_id': PUBLISHER_ID,
        u'message_id': u'67ba0a2a-32bd-4cdf-9bfb-ef9cefcd0f63',
    }


class TestNotification(base.BaseTestCase):
    def _verify_common_sample(self, actual, operation):
        self.assertIsNotNone(actual)
        self.assertEqual('%s.domain.%s' % (notifications.SERVICE, operation),
                         actual.name)
        self.assertEqual(NOW, actual.timestamp)
        self.assertEqual(sample.TYPE_CUMULATIVE, actual.type)
        self.assertEqual(TENANT_ID, actual.project_id)
        self.assertEqual(RESOURCE_ID, actual.resource_id)
        self.assertEqual(USER_ID, actual.user_id)
        metadata = actual.resource_metadata
        self.assertEqual(PUBLISHER_ID, metadata.get('host'))
        self.assertEqual(operation.upper(), metadata.get('action'))
        self.assertEqual(DOMAIN_STATUS, metadata.get('status'))

        self.assertEqual(3600, actual.volume)
        self.assertEqual('s', actual.unit)

    def _test_operation(self, operation):
        notif = _dns_notification_for(operation)
        handler = notifications.DomainExists(mock.Mock())
        data = list(handler.process_notification(notif))
        self.assertEqual(1, len(data))
        self._verify_common_sample(data[0], operation)

    def test_exists(self):
        self._test_operation('exists')
