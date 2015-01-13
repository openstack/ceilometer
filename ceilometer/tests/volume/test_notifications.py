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

from ceilometer import sample
from ceilometer.volume import notifications


def fake_uuid(x):
    return '%s-%s-%s-%s' % (x * 8, x * 4, x * 4, x * 12)


NOW = datetime.datetime.isoformat(datetime.datetime.utcnow())

VOLUME_META = {u'status': u'exists',
               u'instance_uuid': None,
               u'user_id': u'bcb7746c7a41472d88a1ffac89ba6a9b',
               u'availability_zone': u'nova',
               u'tenant_id': u'7ffe17a15c724e2aa79fc839540aec15',
               u'created_at': u'2014-10-28 09:31:20',
               u'volume_id': fake_uuid('c'),
               u'volume_type': u'3a9a398b-7e3b-40da-b09e-2115ad8cd68b',
               u'replication_extended_status': None,
               u'host': u'volumes.example.com',
               u'snapshot_id': None,
               u'replication_status': u'disabled',
               u'size': 1,
               u'display_name': u'2'}

NOTIFICATION_VOLUME_EXISTS = {
    "message_id": "0c65cb9c-018c-11e2-bc91-5453ed1bbb5f",
    "publisher_id": "volumes.example.com",
    "event_type": "volume.exists",
    "priority": "info",
    "payload": VOLUME_META,
    "timestamp": NOW}

NOTIFICATION_VOLUME_CREATE_START = {
    "message_id": "0c65cb9c-018c-11e2-bc91-5453ed1bbb5f",
    "publisher_id": "volumes.example.com",
    "event_type": "volume.create.start",
    "priority": "info",
    "payload": VOLUME_META,
    "timestamp": NOW}

NOTIFICATION_VOLUME_CREATE_END = {
    "message_id": "0c65cb9c-018c-11e2-bc91-5453ed1bbb5f",
    "publisher_id": "volumes.example.com",
    "event_type": "volume.create.end",
    "priority": "info",
    "payload": VOLUME_META,
    "timestamp": NOW}

NOTIFICATION_VOLUME_DELETE_START = {
    "message_id": "0c65cb9c-018c-11e2-bc91-5453ed1bbb5f",
    "publisher_id": "volumes.example.com",
    "event_type": "volume.delete.start",
    "priority": "info",
    "payload": VOLUME_META,
    "timestamp": NOW}

NOTIFICATION_VOLUME_DELETE_END = {
    "message_id": "0c65cb9c-018c-11e2-bc91-5453ed1bbb5f",
    "publisher_id": "volumes.example.com",
    "event_type": "volume.delete.end",
    "priority": "info",
    "payload": VOLUME_META,
    "timestamp": NOW}

NOTIFICATION_VOLUME_RESIZE_START = {
    "message_id": "0c65cb9c-018c-11e2-bc91-5453ed1bbb5f",
    "publisher_id": "volumes.example.com",
    "event_type": "volume.resize.start",
    "priority": "info",
    "payload": VOLUME_META,
    "timestamp": NOW}

NOTIFICATION_VOLUME_RESIZE_END = {
    "message_id": "0c65cb9c-018c-11e2-bc91-5453ed1bbb5f",
    "publisher_id": "volumes.example.com",
    "event_type": "volume.resize.end",
    "priority": "info",
    "payload": VOLUME_META,
    "timestamp": NOW}

NOTIFICATION_VOLUME_ATTACH_START = {
    "message_id": "0c65cb9c-018c-11e2-bc91-5453ed1bbb5f",
    "publisher_id": "volumes.example.com",
    "event_type": "volume.attach.start",
    "priority": "info",
    "payload": VOLUME_META,
    "timestamp": NOW}

NOTIFICATION_VOLUME_ATTACH_END = {
    "message_id": "0c65cb9c-018c-11e2-bc91-5453ed1bbb5f",
    "publisher_id": "volumes.example.com",
    "event_type": "volume.attach.end",
    "priority": "info",
    "payload": VOLUME_META,
    "timestamp": NOW}

NOTIFICATION_VOLUME_DETACH_START = {
    "message_id": "0c65cb9c-018c-11e2-bc91-5453ed1bbb5f",
    "publisher_id": "volumes.example.com",
    "event_type": "volume.detach.start",
    "priority": "info",
    "payload": VOLUME_META,
    "timestamp": NOW}

NOTIFICATION_VOLUME_DETACH_END = {
    "message_id": "0c65cb9c-018c-11e2-bc91-5453ed1bbb5f",
    "publisher_id": "volumes.example.com",
    "event_type": "volume.detach.end",
    "priority": "info",
    "payload": VOLUME_META,
    "timestamp": NOW}

NOTIFICATION_VOLUME_UPDATE_START = {
    "message_id": "0c65cb9c-018c-11e2-bc91-5453ed1bbb5f",
    "publisher_id": "volumes.example.com",
    "event_type": "volume.update.start",
    "priority": "info",
    "payload": VOLUME_META,
    "timestamp": NOW}

NOTIFICATION_VOLUME_UPDATE_END = {
    "message_id": "0c65cb9c-018c-11e2-bc91-5453ed1bbb5f",
    "publisher_id": "volumes.example.com",
    "event_type": "volume.update.end",
    "priority": "info",
    "payload": VOLUME_META,
    "timestamp": NOW}

SNAPSHOT_META = {u'status': u'creating',
                 u'user_id': u'bcb7746c7a41472d88a1ffac89ba6a9b',
                 u'availability_zone': u'nova',
                 u'deleted': u'',
                 u'tenant_id': u'7ffe17a15c724e2aa79fc839540aec15',
                 u'created_at': u'2014-10-28 09:49:07',
                 u'snapshot_id': fake_uuid('c'),
                 u'volume_size': 1,
                 u'volume_id': u'2925bb3b-2b51-496a-bb6e-01a20e950e07',
                 u'display_name': u'11'}

NOTIFICATION_SNAPSHOT_EXISTS = {
    "message_id": "1d2944f9-f8e9-4b2b-8df1-465f759a63e8",
    "publisher_id": "snapshots.example.com",
    "event_type": "snapshot.exists",
    "priority": "info",
    "payload": SNAPSHOT_META,
    "timestamp": NOW}

NOTIFICATION_SNAPSHOT_CREATE_START = {
    "message_id": "1d2944f9-f8e9-4b2b-8df1-465f759a63e8",
    "publisher_id": "snapshots.example.com",
    "event_type": "snapshot.create.start",
    "priority": "info",
    "payload": SNAPSHOT_META,
    "timestamp": NOW}

NOTIFICATION_SNAPSHOT_CREATE_END = {
    "message_id": "1d2944f9-f8e9-4b2b-8df1-465f759a63e8",
    "publisher_id": "snapshots.example.com",
    "event_type": "snapshot.create.end",
    "priority": "info",
    "payload": SNAPSHOT_META,
    "timestamp": NOW}

NOTIFICATION_SNAPSHOT_DELETE_START = {
    "message_id": "1d2944f9-f8e9-4b2b-8df1-465f759a63e8",
    "publisher_id": "snapshots.example.com",
    "event_type": "snapshot.delete.start",
    "priority": "info",
    "payload": SNAPSHOT_META,
    "timestamp": NOW}

NOTIFICATION_SNAPSHOT_DELETE_END = {
    "message_id": "1d2944f9-f8e9-4b2b-8df1-465f759a63e8",
    "publisher_id": "snapshots.example.com",
    "event_type": "snapshot.delete.end",
    "priority": "info",
    "payload": SNAPSHOT_META,
    "timestamp": NOW}

NOTIFICATION_SNAPSHOT_UPDATE_START = {
    "message_id": "1d2944f9-f8e9-4b2b-8df1-465f759a63e8",
    "publisher_id": "snapshots.example.com",
    "event_type": "snapshot.update.start",
    "priority": "info",
    "payload": SNAPSHOT_META,
    "timestamp": NOW}

NOTIFICATION_SNAPSHOT_UPDATE_END = {
    "message_id": "1d2944f9-f8e9-4b2b-8df1-465f759a63e8",
    "publisher_id": "snapshots.example.com",
    "event_type": "snapshot.update.end",
    "priority": "info",
    "payload": SNAPSHOT_META,
    "timestamp": NOW}


class TestNotifications(base.BaseTestCase):

    def setUp(self):
        super(TestNotifications, self).setUp()
        self.host = None
        self.handler_crud = None
        self.handler = None
        self.handler_size = None
        self.name = None
        self.name_size = None
        self.size = None

    def _verify_common_counter(self, c, name, volume):
        self.assertIsNotNone(c)
        self.assertEqual(name, c.name)
        self.assertEqual(fake_uuid('c'), c.resource_id)
        self.assertEqual(NOW, c.timestamp)
        self.assertEqual(volume, c.volume)
        metadata = c.resource_metadata
        self.assertEqual(self.host, metadata.get('host'))

    def _check_crud(self, notification_type, notification_name):
        counters = list(self.handler_crud.process_notification(
            notification_type))
        self.assertEqual(1, len(counters))
        notification = counters[0]
        self._verify_common_counter(
            notification, notification_name, 1)
        self.assertEqual(sample.TYPE_DELTA, notification.type)

    def _check(self, notification_type):
        counters = list(self.handler.process_notification(notification_type))
        self.assertEqual(1, len(counters))
        notification = counters[0]
        self._verify_common_counter(notification, self.name, 1)
        self.assertEqual(sample.TYPE_GAUGE, notification.type)

    def _check_size(self, notification_type):
        counters = list(self.handler_size.process_notification(
            notification_type))
        self.assertEqual(1, len(counters))
        notification = counters[0]
        self._verify_common_counter(
            notification, self.name_size, self.size)
        self.assertEqual(sample.TYPE_GAUGE, notification.type)


class TestVolumeNotifications(TestNotifications):

    def setUp(self):
        super(TestVolumeNotifications, self).setUp()
        self.host = 'volumes.example.com'
        self.handler_crud = notifications.VolumeCRUD(mock.Mock())
        self.handler = notifications.Volume(mock.Mock())
        self.handler_size = notifications.VolumeSize(mock.Mock())
        self.name = 'volume'
        self.name_size = 'volume.size'
        self.size = VOLUME_META['size']

    def test_volume_notifications(self):
        self._check_crud(
            NOTIFICATION_VOLUME_EXISTS, 'volume.exists')
        self._check_crud(
            NOTIFICATION_VOLUME_CREATE_START, 'volume.create.start')
        self._check_crud(
            NOTIFICATION_VOLUME_CREATE_END, 'volume.create.end')
        self._check_crud(
            NOTIFICATION_VOLUME_DELETE_START, 'volume.delete.start')
        self._check_crud(
            NOTIFICATION_VOLUME_DELETE_END, 'volume.delete.end')
        self._check_crud(
            NOTIFICATION_VOLUME_RESIZE_START, 'volume.resize.start')
        self._check_crud(
            NOTIFICATION_VOLUME_RESIZE_END, 'volume.resize.end')
        self._check_crud(
            NOTIFICATION_VOLUME_ATTACH_START, 'volume.attach.start')
        self._check_crud(
            NOTIFICATION_VOLUME_ATTACH_END, 'volume.attach.end')
        self._check_crud(
            NOTIFICATION_VOLUME_DETACH_START, 'volume.detach.start')
        self._check_crud(
            NOTIFICATION_VOLUME_DETACH_END, 'volume.detach.end')
        self._check_crud(
            NOTIFICATION_VOLUME_UPDATE_START, 'volume.update.start')
        self._check_crud(
            NOTIFICATION_VOLUME_UPDATE_END, 'volume.update.end')
        self._check(NOTIFICATION_VOLUME_EXISTS)
        self._check(NOTIFICATION_VOLUME_CREATE_START)
        self._check(NOTIFICATION_VOLUME_CREATE_END)
        self._check(NOTIFICATION_VOLUME_DELETE_START)
        self._check(NOTIFICATION_VOLUME_DELETE_END)
        self._check(NOTIFICATION_VOLUME_RESIZE_START)
        self._check(NOTIFICATION_VOLUME_RESIZE_END)
        self._check(NOTIFICATION_VOLUME_ATTACH_START)
        self._check(NOTIFICATION_VOLUME_ATTACH_END)
        self._check(NOTIFICATION_VOLUME_DETACH_START)
        self._check(NOTIFICATION_VOLUME_DETACH_END)
        self._check(NOTIFICATION_VOLUME_UPDATE_START)
        self._check(NOTIFICATION_VOLUME_UPDATE_END)
        self._check_size(NOTIFICATION_VOLUME_EXISTS)
        self._check_size(NOTIFICATION_VOLUME_CREATE_START)
        self._check_size(NOTIFICATION_VOLUME_CREATE_END)
        self._check_size(NOTIFICATION_VOLUME_DELETE_START)
        self._check_size(NOTIFICATION_VOLUME_DELETE_END)
        self._check_size(NOTIFICATION_VOLUME_RESIZE_START)
        self._check_size(NOTIFICATION_VOLUME_RESIZE_END)
        self._check_size(NOTIFICATION_VOLUME_ATTACH_START)
        self._check_size(NOTIFICATION_VOLUME_ATTACH_END)
        self._check_size(NOTIFICATION_VOLUME_DETACH_START)
        self._check_size(NOTIFICATION_VOLUME_DETACH_END)
        self._check_size(NOTIFICATION_VOLUME_UPDATE_START)
        self._check_size(NOTIFICATION_VOLUME_UPDATE_END)


class TestSnapshotNotifications(TestNotifications):

    def setUp(self):
        super(TestSnapshotNotifications, self).setUp()
        self.host = 'snapshots.example.com'
        self.handler_crud = notifications.SnapshotCRUD(mock.Mock())
        self.handler = notifications.Snapshot(mock.Mock())
        self.handler_size = notifications.SnapshotSize(mock.Mock())
        self.name = 'snapshot'
        self.name_size = 'snapshot.size'
        self.size = SNAPSHOT_META['volume_size']

    def test_snapshot_notifications(self):
        self._check_crud(
            NOTIFICATION_SNAPSHOT_EXISTS, 'snapshot.exists')
        self._check_crud(
            NOTIFICATION_SNAPSHOT_CREATE_START, 'snapshot.create.start')
        self._check_crud(
            NOTIFICATION_SNAPSHOT_CREATE_END, 'snapshot.create.end')
        self._check_crud(
            NOTIFICATION_SNAPSHOT_DELETE_START, 'snapshot.delete.start')
        self._check_crud(
            NOTIFICATION_SNAPSHOT_DELETE_END, 'snapshot.delete.end')
        self._check_crud(
            NOTIFICATION_SNAPSHOT_UPDATE_START, 'snapshot.update.start')
        self._check_crud(
            NOTIFICATION_SNAPSHOT_UPDATE_END, 'snapshot.update.end')
        self._check(NOTIFICATION_SNAPSHOT_EXISTS)
        self._check(NOTIFICATION_SNAPSHOT_CREATE_START)
        self._check(NOTIFICATION_SNAPSHOT_CREATE_END)
        self._check(NOTIFICATION_SNAPSHOT_DELETE_START)
        self._check(NOTIFICATION_SNAPSHOT_DELETE_END)
        self._check(NOTIFICATION_SNAPSHOT_UPDATE_START)
        self._check(NOTIFICATION_SNAPSHOT_UPDATE_END)
        self._check_size(NOTIFICATION_SNAPSHOT_EXISTS)
        self._check_size(NOTIFICATION_SNAPSHOT_CREATE_START)
        self._check_size(NOTIFICATION_SNAPSHOT_CREATE_END)
        self._check_size(NOTIFICATION_SNAPSHOT_DELETE_START)
        self._check_size(NOTIFICATION_SNAPSHOT_DELETE_END)
        self._check_size(NOTIFICATION_SNAPSHOT_UPDATE_START)
        self._check_size(NOTIFICATION_SNAPSHOT_UPDATE_END)
