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

import datetime

import mock
from oslotest import base

from ceilometer.identity import notifications
from ceilometer import sample


NOW = datetime.datetime.isoformat(datetime.datetime.utcnow())

PROJECT_ID = u'project_id'
USER_ID = u'user_id'
ROLE_ID = u'role_id'
GROUP_ID = u'group_id'
TRUST_ID = u'trust_id'
PUBLISHER_ID = u'identity.node-n5x66lxdy67d'


def notification_for(resource_type, operation, resource_id):

    return {
        u'event_type': '%s.%s.%s' % (notifications.SERVICE, resource_type,
                                     operation),
        u'message_id': u'ef921faa-7f7b-4854-8b86-a424ab93c96e',
        u'payload': {
            u'resource_info': resource_id
        },
        u'priority': u'INFO',
        u'publisher_id': PUBLISHER_ID,
        u'timestamp': NOW
    }


def authn_notification_for(outcome):

    return {
        u'event_type': u'identity.authenticate',
        u'message_id': u'1371a590-d5fd-448f-b3bb-a14dead6f4cb',
        u'payload': {
            u'typeURI': u'http://schemas.dmtf.org/cloud/audit/1.0/event',
            u'initiator': {
                u'typeURI': u'service/security/account/user',
                u'host': {
                    u'agent': u'python-keystoneclient',
                    u'address': u'10.0.2.15'
                },
                u'id': USER_ID,
                u'name': u'openstack:demo_user'
            },
            u'target': {
                u'typeURI': u'service/security/account/user',
                u'id': u'openstack:44b3d8cb-5f16-46e9-9b1b-ac90b64c2530'
            },
            u'observer': {
                u'typeURI': u'service/security',
                u'id': u'openstack:55a9e88c-a4b1-4864-9339-62b7e6ecb6a7'
            },
            u'eventType': u'activity',
            u'eventTime': u'2014-08-04T05:38:59.978898+0000',
            u'action': u'authenticate',
            u'outcome': outcome,
            u'id': u'openstack:eca02fef-9394-4008-8fb3-c434133ca4b2'
        },
        u'priority': u'INFO',
        u'publisher_id': PUBLISHER_ID,
        u'timestamp': NOW
    }


class TestCRUDNotification(base.BaseTestCase):

    def _verify_common_sample(self, s):
        self.assertIsNotNone(s)
        self.assertEqual(NOW, s.timestamp)
        self.assertEqual(sample.TYPE_DELTA, s.type)
        self.assertIsNone(s.project_id)
        self.assertIsNone(s.user_id)
        metadata = s.resource_metadata
        self.assertEqual(PUBLISHER_ID, metadata.get('host'))

    def _test_operation(self, resource_type, operation, resource_id,
                        notification_class):
        notif = notification_for(resource_type, operation, resource_id)
        handler = notification_class(mock.Mock())
        data = list(handler.process_notification(notif))
        self.assertEqual(1, len(data))
        self.assertEqual(resource_id, data[0].resource_id)
        name = '%s.%s.%s' % (notifications.SERVICE, resource_type, operation)
        self.assertEqual(name, data[0].name)
        self._verify_common_sample(data[0])

    def test_create_user(self):
        self._test_operation('user', 'created', USER_ID, notifications.User)

    def test_delete_user(self):
        self._test_operation('user', 'deleted', USER_ID, notifications.User)

    def test_update_user(self):
        self._test_operation('user', 'updated', USER_ID, notifications.User)

    def test_create_group(self):
        self._test_operation('group', 'created', GROUP_ID, notifications.Group)

    def test_update_group(self):
        self._test_operation('group', 'updated', GROUP_ID, notifications.Group)

    def test_delete_group(self):
        self._test_operation('group', 'deleted', GROUP_ID, notifications.Group)

    def test_create_project(self):
        self._test_operation('project', 'created', PROJECT_ID,
                             notifications.Project)

    def test_update_project(self):
        self._test_operation('project', 'updated', PROJECT_ID,
                             notifications.Project)

    def test_delete_project(self):
        self._test_operation('project', 'deleted', PROJECT_ID,
                             notifications.Project)

    def test_create_role(self):
        self._test_operation('role', 'deleted', ROLE_ID, notifications.Role)

    def test_update_role(self):
        self._test_operation('role', 'updated', ROLE_ID, notifications.Role)

    def test_delete_role(self):
        self._test_operation('role', 'deleted', ROLE_ID, notifications.Role)

    def test_create_trust(self):
        self._test_operation('trust', 'created', TRUST_ID, notifications.Trust)

    def test_delete_trust(self):
        self._test_operation('trust', 'deleted', TRUST_ID, notifications.Trust)


class TestAuthenticationNotification(base.BaseTestCase):

    def _verify_common_sample(self, s):
        self.assertIsNotNone(s)
        self.assertEqual(NOW, s.timestamp)
        self.assertEqual(sample.TYPE_DELTA, s.type)
        self.assertIsNone(s.project_id)
        self.assertEqual(USER_ID, s.user_id)
        self.assertEqual(USER_ID, s.resource_id)
        self.assertEqual('user', s.unit)
        metadata = s.resource_metadata
        self.assertEqual(PUBLISHER_ID, metadata.get('host'))

    def _test_operation(self, outcome):
        notif = authn_notification_for(outcome)
        handler = notifications.Authenticate(mock.Mock())
        data = list(handler.process_notification(notif))
        self.assertEqual(1, len(data))
        name = '%s.%s.%s' % (notifications.SERVICE, 'authenticate', outcome)
        self.assertEqual(name, data[0].name)
        self._verify_common_sample(data[0])

    def test_authn_success(self):
        self._test_operation('success')

    def test_authn_failure(self):
        self._test_operation('failure')

    def test_authn_pending(self):
        self._test_operation('pending')
