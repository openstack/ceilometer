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
"""Tests for swift notification events."""
import mock

from ceilometer.objectstore import notifications
from ceilometer.tests import base as test


MIDDLEWARE_EVENT = {
    u'_context_request_id': u'req-a8bfa89b-d28b-4b95-9e4b-7d7875275650',
    u'_context_quota_class': None,
    u'event_type': u'objectstore.http.request',
    u'_context_service_catalog': [],
    u'_context_auth_token': None,
    u'_context_user_id': None,
    u'priority': u'INFO',
    u'_context_is_admin': True,
    u'_context_user': None,
    u'publisher_id': u'ceilometermiddleware',
    u'message_id': u'6eccedba-120e-4db8-9735-2ad5f061e5ee',
    u'_context_remote_address': None,
    u'_context_roles': [],
    u'timestamp': u'2013-07-29 06:51:34.474815',
    u'_context_timestamp': u'2013-07-29T06:51:34.348091',
    u'_unique_id': u'0ee26117077648e18d88ac76e28a72e2',
    u'_context_project_name': None,
    u'_context_read_deleted': u'no',
    u'_context_tenant': None,
    u'_context_instance_lock_checked': False,
    u'_context_project_id': None,
    u'_context_user_name': None,
    u'payload': {
        'typeURI': 'http: //schemas.dmtf.org/cloud/audit/1.0/event',
        'eventTime': '2015-01-30T16: 38: 43.233621',
        'target': {
            'action': 'get',
            'typeURI': 'service/storage/object',
            'id': 'account',
            'metadata': {
                'path': '/1.0/CUSTOM_account/container/obj',
                'version': '1.0',
                'container': 'container',
                'object': 'obj'
            }
        },
        'observer': {
            'id': 'target'
        },
        'eventType': 'activity',
        'measurements': [
            {
                'metric': {
                    'metricId': 'openstack: uuid',
                    'name': 'storage.objects.outgoing.bytes',
                    'unit': 'B'
                },
                'result': 28
            },
            {
                'metric': {
                    'metricId': 'openstack: uuid2',
                    'name': 'storage.objects.incoming.bytes',
                    'unit': 'B'
                },
                'result': 1
            }
        ],
        'initiator': {
            'typeURI': 'service/security/account/user',
            'project_id': None,
            'id': 'openstack: 288f6260-bf37-4737-a178-5038c84ba244'
        },
        'action': 'read',
        'outcome': 'success',
        'id': 'openstack: 69972bb6-14dd-46e4-bdaf-3148014363dc'
    }
}


class TestMiddlewareNotifications(test.BaseTestCase):
    def test_middleware_event(self):
        v = notifications.SwiftWsgiMiddleware(mock.Mock())
        samples = list(v.process_notification(MIDDLEWARE_EVENT))
        self.assertEqual(1, len(samples))
        target = MIDDLEWARE_EVENT['payload']['target']
        initiator = MIDDLEWARE_EVENT['payload']['initiator']
        self.assertEqual(target['id'], samples[0].resource_id)
        self.assertEqual(initiator['id'], samples[0].user_id)
        self.assertEqual(initiator['project_id'], samples[0].project_id)
