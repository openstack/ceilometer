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

from ceilometer.key_value_storage import notifications
from ceilometer import sample


def fake_uuid(x):
    return '%s-%s-%s-%s' % (x * 8, x * 4, x * 4, x * 12)


NOW = datetime.datetime.isoformat(datetime.datetime.utcnow())


TABLE_CREATE_PAYLOAD = {
    u'table_uuid': fake_uuid('r'),
    u'index_count': 2,
    u'table_name': u'email_data'
    }

TABLE_DELETE_PAYLOAD = {
    u'table_uuid': fake_uuid('r'),
    u'table_name': u'email_data'
    }

NOTIFICATION_TABLE_CREATE = {
    u'_context_request_id': u'req-d6e9b7ec-976f-443f-ba6e-e2b89b18aa75',
    u'_context_tenant': fake_uuid('t'),
    u'_context_user': fake_uuid('u'),
    u'_context_auth_token': u'',
    u'_context_show_deleted': False,
    u'_context_is_admin': u'False',
    u'_context_read_only': False,
    'payload': TABLE_CREATE_PAYLOAD,
    'publisher_id': u'magnetodb.winterfell.com',
    'message_id': u'3d71fb8a-f1d7-4a4e-b29f-7a711a761ba1',
    'event_type': u'magnetodb.table.create.end',
    'timestamp': NOW,
    'priority': 'info'
    }

NOTIFICATION_TABLE_DELETE = {
    u'_context_request_id': u'req-d6e9b7ec-976f-443f-ba6e-e2b89b18aa75',
    u'_context_tenant': fake_uuid('t'),
    u'_context_user': fake_uuid('u'),
    u'_context_auth_token': u'',
    u'_context_show_deleted': False,
    u'_context_is_admin': u'False',
    u'_context_read_only': False,
    'payload': TABLE_DELETE_PAYLOAD,
    'publisher_id': u'magnetodb.winterfell.com',
    'message_id': u'4c8f5940-3c90-41af-ac16-f0e3055a305d',
    'event_type': u'magnetodb.table.delete.end',
    'timestamp': NOW,
    'priority': 'info'
    }


class TestNotification(base.BaseTestCase):

    def _verify_common_counter(self, c, name, volume):
        self.assertIsNotNone(c)
        self.assertEqual(name, c.name)
        self.assertEqual(fake_uuid('r'), c.resource_id)
        self.assertEqual(NOW, c.timestamp)
        self.assertEqual(volume, c.volume)
        metadata = c.resource_metadata
        self.assertEqual(u'magnetodb.winterfell.com', metadata.get('host'))

    def test_create_table(self):
        handler = notifications.Table(mock.Mock())
        counters = list(handler.process_notification(
                        NOTIFICATION_TABLE_CREATE))
        self.assertEqual(1, len(counters))
        table = counters[0]
        self._verify_common_counter(table, 'magnetodb.table.create', 1)
        self.assertEqual(fake_uuid('u'), table.user_id)
        self.assertEqual(fake_uuid('t'), table.project_id)
        self.assertEqual(sample.TYPE_GAUGE, table.type)

    def test_delete_table(self):
        handler = notifications.Table(mock.Mock())
        counters = list(handler.process_notification(
                        NOTIFICATION_TABLE_DELETE))
        self.assertEqual(1, len(counters))
        table = counters[0]
        self._verify_common_counter(table, 'magnetodb.table.delete', 1)
        self.assertEqual(fake_uuid('u'), table.user_id)
        self.assertEqual(fake_uuid('t'), table.project_id)
        self.assertEqual(sample.TYPE_GAUGE, table.type)

    def test_index_count(self):
        handler = notifications.Index(mock.Mock())
        counters = list(handler.process_notification(
                        NOTIFICATION_TABLE_CREATE))
        self.assertEqual(1, len(counters))
        table = counters[0]
        self._verify_common_counter(table, 'magnetodb.table.index.count', 2)
        self.assertEqual(fake_uuid('u'), table.user_id)
        self.assertEqual(fake_uuid('t'), table.project_id)
        self.assertEqual(sample.TYPE_GAUGE, table.type)
