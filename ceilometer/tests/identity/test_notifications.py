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

from ceilometer.identity import notifications
from ceilometer.openstack.common import test
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


class TestNotification(test.BaseTestCase):

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
