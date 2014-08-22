#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mock
from oslotest import base

from ceilometer.volume import notifications

NOTIFICATION_VOLUME_EXISTS = {
    u'_context_roles': [u'admin'],
    u'_context_request_id': u'req-7ef29a5d-adeb-48a8-b104-59c05361aa27',
    u'_context_quota_class': None,
    u'event_type': u'volume.exists',
    u'timestamp': u'2012-09-21 09:29:10.620731',
    u'message_id': u'e0e6a5ad-2fc9-453c-b3fb-03fe504538dc',
    u'_context_auth_token': None,
    u'_context_is_admin': True,
    u'_context_project_id': None,
    u'_context_timestamp': u'2012-09-21T09:29:10.266928',
    u'_context_read_deleted': u'no',
    u'_context_user_id': None,
    u'_context_remote_address': None,
    u'publisher_id': u'volume.ubuntu-VirtualBox',
    u'payload': {u'status': u'available',
                 u'audit_period_beginning': u'2012-09-20 00:00:00',
                 u'display_name': u'volume1',
                 u'tenant_id': u'6c97f1ecf17047eab696786d56a0bff5',
                 u'created_at': u'2012-09-20 15:05:16',
                 u'snapshot_id': None,
                 u'volume_type': None,
                 u'volume_id': u'84c363b9-9854-48dc-b949-fe04263f4cf0',
                 u'audit_period_ending': u'2012-09-21 00:00:00',
                 u'user_id': u'4d2fa4b76a4a4ecab8c468c8dea42f89',
                 u'launched_at': u'2012-09-20 15:05:23',
                 u'size': 2},
    u'priority': u'INFO'
}

NOTIFICATION_VOLUME_DELETE = {
    u'_context_roles': [u'Member', u'admin'],
    u'_context_request_id': u'req-6ba8ccb4-1093-4a39-b029-adfaa3fc7ceb',
    u'_context_quota_class': None,
    u'event_type': u'volume.delete.start',
    u'timestamp': u'2012-09-21 10:24:13.168630',
    u'message_id': u'f6e6bc1f-fcd5-41e1-9a86-da7d024f03d9',
    u'_context_auth_token': u'277c6899de8a4b3d999f3e2e4c0915ff',
    u'_context_is_admin': True,
    u'_context_project_id': u'6c97f1ecf17047eab696786d56a0bff5',
    u'_context_timestamp': u'2012-09-21T10:23:54.741228',
    u'_context_read_deleted': u'no',
    u'_context_user_id': u'4d2fa4b76a4a4ecab8c468c8dea42f89',
    u'_context_remote_address': u'192.168.22.101',
    u'publisher_id': u'volume.ubuntu-VirtualBox',
    u'payload': {u'status': u'deleting',
                 u'volume_type_id': None,
                 u'display_name': u'abc',
                 u'tenant_id': u'6c97f1ecf17047eab696786d56a0bff5',
                 u'created_at': u'2012-09-21 10:10:47',
                 u'snapshot_id': None,
                 u'volume_id': u'3b761164-84b4-4eb3-8fcb-1974c641d6ef',
                 u'user_id': u'4d2fa4b76a4a4ecab8c468c8dea42f89',
                 u'launched_at': u'2012-09-21 10:10:50',
                 u'size': 3},
    u'priority': u'INFO'}


NOTIFICATION_VOLUME_ATTACH = {
    u'_context_roles': [u'Member', u'admin'],
    u'_context_request_id': u'req-6ba8ccb4-1093-4a39-b029-adfaa3fc7ceb',
    u'_context_quota_class': None,
    u'event_type': u'volume.attach.end',
    u'timestamp': u'2012-09-21 10:24:13.168630',
    u'message_id': u'c994ae8d-d068-4101-bd06-1048877c844a',
    u'_context_auth_token': u'277c6899de8a4b3d999f3e2e4c0915ff',
    u'_context_is_admin': True,
    u'_context_project_id': u'6c97f1ecf17047eab696786d56a0bff5',
    u'_context_timestamp': u'2012-09-21T10:02:27.134211',
    u'_context_read_deleted': u'no',
    u'_context_user_id': u'4d2fa4b76a4a4ecab8c468c8dea42f89',
    u'_context_remote_address': u'192.168.22.101',
    u'publisher_id': u'volume.ubuntu-VirtualBox',
    u'payload': {u'status': u'in-use',
                 u'volume_type_id': None,
                 u'display_name': u'abc',
                 u'tenant_id': u'6c97f1ecf17047eab696786d56a0bff5',
                 u'created_at': u'2012-09-21 10:10:47',
                 u'snapshot_id': None,
                 u'volume_id': u'3b761164-84b4-4eb3-8fcb-1974c641d6ef',
                 u'user_id': u'4d2fa4b76a4a4ecab8c468c8dea42f89',
                 u'launched_at': u'2012-09-21 10:10:50',
                 u'size': 3},
    u'priority': u'INFO'}


NOTIFICATION_VOLUME_DETACH = {
    u'_context_roles': [u'Member', u'admin'],
    u'_context_request_id': u'req-6ba8ccb4-1093-4a39-b029-adfaa3fc7ceb',
    u'_context_quota_class': None,
    u'event_type': u'volume.detach.end',
    u'timestamp': u'2012-09-21 10:24:13.168630',
    u'message_id': u'c994ae8d-d068-4101-bd06-1048877c844a',
    u'_context_auth_token': u'277c6899de8a4b3d999f3e2e4c0915ff',
    u'_context_is_admin': True,
    u'_context_project_id': u'6c97f1ecf17047eab696786d56a0bff5',
    u'_context_timestamp': u'2012-09-21T10:02:27.134211',
    u'_context_read_deleted': u'no',
    u'_context_user_id': u'4d2fa4b76a4a4ecab8c468c8dea42f89',
    u'_context_remote_address': u'192.168.22.101',
    u'publisher_id': u'volume.ubuntu-VirtualBox',
    u'payload': {u'status': u'available',
                 u'volume_type_id': None,
                 u'display_name': u'abc',
                 u'tenant_id': u'6c97f1ecf17047eab696786d56a0bff5',
                 u'created_at': u'2012-09-21 10:10:47',
                 u'snapshot_id': None,
                 u'volume_id': u'3b761164-84b4-4eb3-8fcb-1974c641d6ef',
                 u'user_id': u'4d2fa4b76a4a4ecab8c468c8dea42f89',
                 u'launched_at': u'2012-09-21 10:10:50',
                 u'size': 3},
    u'priority': u'INFO'}


NOTIFICATION_VOLUME_RESIZE = {
    u'_context_roles': [u'Member', u'admin'],
    u'_context_request_id': u'req-6ba8ccb4-1093-4a39-b029-adfaa3fc7ceb',
    u'_context_quota_class': None,
    u'event_type': u'volume.resize.end',
    u'timestamp': u'2012-09-21 10:24:13.168630',
    u'message_id': u'b5814258-3425-4eb7-b6b7-bf4811203e58',
    u'_context_auth_token': u'277c6899de8a4b3d999f3e2e4c0915ff',
    u'_context_is_admin': True,
    u'_context_project_id': u'6c97f1ecf17047eab696786d56a0bff5',
    u'_context_timestamp': u'2012-09-21T10:02:27.134211',
    u'_context_read_deleted': u'no',
    u'_context_user_id': u'4d2fa4b76a4a4ecab8c468c8dea42f89',
    u'_context_remote_address': u'192.168.22.101',
    u'publisher_id': u'volume.ubuntu-VirtualBox',
    u'payload': {u'status': u'extending',
                 u'volume_type_id': None,
                 u'display_name': u'abc',
                 u'tenant_id': u'6c97f1ecf17047eab696786d56a0bff5',
                 u'created_at': u'2012-09-21 10:10:47',
                 u'snapshot_id': None,
                 u'volume_id': u'3b761164-84b4-4eb3-8fcb-1974c641d6ef',
                 u'user_id': u'4d2fa4b76a4a4ecab8c468c8dea42f89',
                 u'launched_at': u'2012-09-21 10:10:50',
                 u'size': 3},
    u'priority': u'INFO'}


NOTIFICATION_SNAPSHOT_EXISTS = {
    u'_context_roles': [u'admin'],
    u'_context_request_id': u'req-7ef29a5d-adeb-48a8-b104-59c05361aa27',
    u'_context_quota_class': None,
    u'event_type': u'snapshot.exists',
    u'timestamp': u'2012-09-21 09:29:10.620731',
    u'message_id': u'e0e6a5ad-2fc9-453c-b3fb-03fe504538dc',
    u'_context_auth_token': None,
    u'_context_is_admin': True,
    u'_context_project_id': None,
    u'_context_timestamp': u'2012-09-21T09:29:10.266928',
    u'_context_read_deleted': u'no',
    u'_context_user_id': None,
    u'_context_remote_address': None,
    u'publisher_id': u'volume.ubuntu-VirtualBox',
    u"payload": {u"audit_period_beginning": u"2014-05-06 11:00:00",
                 u"audit_period_ending": u"2014-05-06 12:00:00",
                 u"availability_zone": u"left",
                 u"created_at": u"2014-05-06 09:33:43",
                 u"deleted": u"",
                 u"display_name": "lil snapshot",
                 u"snapshot_id": u"dd163129-9476-4cf5-9311-dd425324d8d8",
                 u"status": u"available",
                 u"tenant_id": u"compliance",
                 u"user_id": u"e0271f64847b49429bb304c775c7427a",
                 u"volume_id": u"b96e026e-c9bf-4418-8d6f-4ba493bbb7d6",
                 u"volume_size": 3},
    u'priority': u'INFO'}


class TestNotifications(base.BaseTestCase):

    def _verify_common_sample_volume(self, s, name, notification):
        self.assertIsNotNone(s)
        self.assertEqual(s.name, name)
        self.assertEqual(notification['payload']['volume_id'], s.resource_id)
        self.assertEqual(notification['timestamp'], s.timestamp)
        metadata = s.resource_metadata
        self.assertEqual(notification['publisher_id'], metadata.get('host'))

    def test_volume_exists(self):
        v = notifications.Volume(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_VOLUME_EXISTS))
        self.assertEqual(1, len(samples))
        s = samples[0]
        self._verify_common_sample_volume(
            s, 'volume', NOTIFICATION_VOLUME_EXISTS)
        self.assertEqual(1, s.volume)

    def test_volume_size_exists(self):
        v = notifications.VolumeSize(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_VOLUME_EXISTS))
        self.assertEqual(1, len(samples))
        s = samples[0]
        self._verify_common_sample_volume(s, 'volume.size',
                                          NOTIFICATION_VOLUME_EXISTS)
        self.assertEqual(NOTIFICATION_VOLUME_EXISTS['payload']['size'],
                         s.volume)

    def test_volume_delete(self):
        v = notifications.Volume(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_VOLUME_DELETE))
        self.assertEqual(1, len(samples))
        s = samples[0]
        self._verify_common_sample_volume(
            s, 'volume', NOTIFICATION_VOLUME_DELETE)
        self.assertEqual(1, s.volume)

    def test_volume_size_delete(self):
        v = notifications.VolumeSize(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_VOLUME_DELETE))
        self.assertEqual(1, len(samples))
        s = samples[0]
        self._verify_common_sample_volume(s, 'volume.size',
                                          NOTIFICATION_VOLUME_DELETE)
        self.assertEqual(NOTIFICATION_VOLUME_DELETE['payload']['size'],
                         s.volume)

    def test_volume_attach(self):
        v = notifications.Volume(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_VOLUME_ATTACH))
        self.assertEqual(1, len(samples))
        s = samples[0]
        self._verify_common_sample_volume(
            s, 'volume', NOTIFICATION_VOLUME_ATTACH)
        self.assertEqual(1, s.volume)

    def test_volume_size_attach(self):
        v = notifications.VolumeSize(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_VOLUME_ATTACH))
        self.assertEqual(1, len(samples))
        s = samples[0]
        self._verify_common_sample_volume(s, 'volume.size',
                                          NOTIFICATION_VOLUME_ATTACH)
        self.assertEqual(NOTIFICATION_VOLUME_ATTACH['payload']['size'],
                         s.volume)

    def test_volume_detach(self):
        v = notifications.Volume(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_VOLUME_DETACH))
        self.assertEqual(1, len(samples))
        s = samples[0]
        self._verify_common_sample_volume(
            s, 'volume', NOTIFICATION_VOLUME_ATTACH)
        self.assertEqual(1, s.volume)

    def test_volume_size_detach(self):
        v = notifications.VolumeSize(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_VOLUME_DETACH))
        self.assertEqual(1, len(samples))
        s = samples[0]
        self._verify_common_sample_volume(s, 'volume.size',
                                          NOTIFICATION_VOLUME_DETACH)
        self.assertEqual(NOTIFICATION_VOLUME_DETACH['payload']['size'],
                         s.volume)

    def test_volume_resize(self):
        v = notifications.Volume(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_VOLUME_RESIZE))
        self.assertEqual(1, len(samples))
        s = samples[0]
        self._verify_common_sample_volume(
            s, 'volume', NOTIFICATION_VOLUME_RESIZE)
        self.assertEqual(1, s.volume)

    def test_volume_size_resize(self):
        v = notifications.VolumeSize(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_VOLUME_RESIZE))
        self.assertEqual(1, len(samples))
        s = samples[0]
        self._verify_common_sample_volume(s, 'volume.size',
                                          NOTIFICATION_VOLUME_RESIZE)
        self.assertEqual(NOTIFICATION_VOLUME_RESIZE['payload']['size'],
                         s.volume)

    def _verify_common_sample_snapshot(self, s, name, notification):
        self.assertIsNotNone(s)
        self.assertEqual(name, s.name)
        self.assertEqual(notification['payload']['snapshot_id'], s.resource_id)
        self.assertEqual(notification['timestamp'], s.timestamp)
        metadata = s.resource_metadata
        self.assertEqual(notification['publisher_id'], metadata.get('host'))

    def test_snapshot_exists(self):
        v = notifications.Snapshot(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_SNAPSHOT_EXISTS))
        self.assertEqual(1, len(samples))
        s = samples[0]
        self._verify_common_sample_snapshot(s, 'snapshot',
                                            NOTIFICATION_SNAPSHOT_EXISTS)
        self.assertEqual(1, s.volume)

    def test_snapshot_size_exists(self):
        v = notifications.SnapshotSize(mock.Mock())
        samples = list(v.process_notification(NOTIFICATION_SNAPSHOT_EXISTS))
        self.assertEqual(1, len(samples))
        s = samples[0]
        self._verify_common_sample_snapshot(s, 'snapshot.size',
                                            NOTIFICATION_SNAPSHOT_EXISTS)
        volume_size = NOTIFICATION_SNAPSHOT_EXISTS['payload']['volume_size']
        self.assertEqual(volume_size, s.volume)
