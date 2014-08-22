#
# Copyright 2012 Red Hat Inc.
#
# Author: Eoghan Glynn <eglynn@redhat.com>
# Author: Julien danjou <julien@danjou.info>
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

import datetime

import mock
from oslotest import base

from ceilometer.image import notifications
from ceilometer import sample


def fake_uuid(x):
    return '%s-%s-%s-%s' % (x * 8, x * 4, x * 4, x * 12)


NOW = datetime.datetime.isoformat(datetime.datetime.utcnow())

NOTIFICATION_SEND = {
    u'event_type': u'image.send',
    u'timestamp': NOW,
    u'message_id': fake_uuid('a'),
    u'priority': u'INFO',
    u'publisher_id': u'images.example.com',
    u'payload': {u'receiver_tenant_id': fake_uuid('b'),
                 u'destination_ip': u'1.2.3.4',
                 u'bytes_sent': 42,
                 u'image_id': fake_uuid('c'),
                 u'receiver_user_id': fake_uuid('d'),
                 u'owner_id': fake_uuid('e')}
}

IMAGE_META = {u'status': u'saving',
              u'name': u'fake image #3',
              u'deleted': False,
              u'container_format': u'ovf',
              u'created_at': u'2012-09-18T10:13:44.571370',
              u'disk_format': u'vhd',
              u'updated_at': u'2012-09-18T10:13:44.623120',
              u'properties': {u'key2': u'value2',
                              u'key1': u'value1'},
              u'min_disk': 0,
              u'protected': False,
              u'id': fake_uuid('c'),
              u'location': None,
              u'checksum': u'd990432ef91afef3ad9dbf4a975d3365',
              u'owner': "fake",
              u'is_public': False,
              u'deleted_at': None,
              u'min_ram': 0,
              u'size': 19}


NOTIFICATION_UPDATE = {"message_id": "0c65cb9c-018c-11e2-bc91-5453ed1bbb5f",
                       "publisher_id": "images.example.com",
                       "event_type": "image.update",
                       "priority": "info",
                       "payload": IMAGE_META,
                       "timestamp": NOW}


NOTIFICATION_UPLOAD = {"message_id": "0c65cb9c-018c-11e2-bc91-5453ed1bbb5f",
                       "publisher_id": "images.example.com",
                       "event_type": "image.upload",
                       "priority": "info",
                       "payload": IMAGE_META,
                       "timestamp": NOW}


NOTIFICATION_DELETE = {"message_id": "0c65cb9c-018c-11e2-bc91-5453ed1bbb5f",
                       "publisher_id": "images.example.com",
                       "event_type": "image.delete",
                       "priority": "info",
                       "payload": IMAGE_META,
                       "timestamp": NOW}


class TestNotification(base.BaseTestCase):

    def _verify_common_counter(self, c, name, volume):
        self.assertIsNotNone(c)
        self.assertEqual(c.name, name)
        self.assertEqual(fake_uuid('c'), c.resource_id)
        self.assertEqual(NOW, c.timestamp)
        self.assertEqual(volume, c.volume)
        metadata = c.resource_metadata
        self.assertEqual(u'images.example.com', metadata.get('host'))

    def test_image_download(self):
        handler = notifications.ImageDownload(mock.Mock())
        counters = list(handler.process_notification(NOTIFICATION_SEND))
        self.assertEqual(1, len(counters))
        download = counters[0]
        self._verify_common_counter(download, 'image.download', 42)
        self.assertEqual(fake_uuid('d'), download.user_id)
        self.assertEqual(fake_uuid('b'), download.project_id)
        self.assertEqual(sample.TYPE_DELTA, download.type)

    def test_image_serve(self):
        handler = notifications.ImageServe(mock.Mock())
        counters = list(handler.process_notification(NOTIFICATION_SEND))
        self.assertEqual(1, len(counters))
        serve = counters[0]
        self._verify_common_counter(serve, 'image.serve', 42)
        self.assertEqual(fake_uuid('e'), serve.project_id)
        self.assertEqual(fake_uuid('d'),
                         serve.resource_metadata.get('receiver_user_id'))
        self.assertEqual(fake_uuid('b'),
                         serve.resource_metadata.get('receiver_tenant_id'))
        self.assertEqual(sample.TYPE_DELTA, serve.type)

    def test_image_crud_on_update(self):
        handler = notifications.ImageCRUD(mock.Mock())
        counters = list(handler.process_notification(NOTIFICATION_UPDATE))
        self.assertEqual(1, len(counters))
        update = counters[0]
        self._verify_common_counter(update, 'image.update', 1)
        self.assertEqual(sample.TYPE_DELTA, update.type)

    def test_image_on_update(self):
        handler = notifications.Image(mock.Mock())
        counters = list(handler.process_notification(NOTIFICATION_UPDATE))
        self.assertEqual(1, len(counters))
        update = counters[0]
        self._verify_common_counter(update, 'image', 1)
        self.assertEqual(sample.TYPE_GAUGE, update.type)

    def test_image_size_on_update(self):
        handler = notifications.ImageSize(mock.Mock())
        counters = list(handler.process_notification(NOTIFICATION_UPDATE))
        self.assertEqual(1, len(counters))
        update = counters[0]
        self._verify_common_counter(update, 'image.size',
                                    IMAGE_META['size'])
        self.assertEqual(sample.TYPE_GAUGE, update.type)

    def test_image_crud_on_upload(self):
        handler = notifications.ImageCRUD(mock.Mock())
        counters = list(handler.process_notification(NOTIFICATION_UPLOAD))
        self.assertEqual(1, len(counters))
        upload = counters[0]
        self._verify_common_counter(upload, 'image.upload', 1)
        self.assertEqual(sample.TYPE_DELTA, upload.type)

    def test_image_on_upload(self):
        handler = notifications.Image(mock.Mock())
        counters = list(handler.process_notification(NOTIFICATION_UPLOAD))
        self.assertEqual(1, len(counters))
        upload = counters[0]
        self._verify_common_counter(upload, 'image', 1)
        self.assertEqual(sample.TYPE_GAUGE, upload.type)

    def test_image_size_on_upload(self):
        handler = notifications.ImageSize(mock.Mock())
        counters = list(handler.process_notification(NOTIFICATION_UPLOAD))
        self.assertEqual(1, len(counters))
        upload = counters[0]
        self._verify_common_counter(upload, 'image.size',
                                    IMAGE_META['size'])
        self.assertEqual(sample.TYPE_GAUGE, upload.type)

    def test_image_crud_on_delete(self):
        handler = notifications.ImageCRUD(mock.Mock())
        counters = list(handler.process_notification(NOTIFICATION_DELETE))
        self.assertEqual(1, len(counters))
        delete = counters[0]
        self._verify_common_counter(delete, 'image.delete', 1)
        self.assertEqual(sample.TYPE_DELTA, delete.type)

    def test_image_on_delete(self):
        handler = notifications.Image(mock.Mock())
        counters = list(handler.process_notification(NOTIFICATION_DELETE))
        self.assertEqual(1, len(counters))
        delete = counters[0]
        self._verify_common_counter(delete, 'image', 1)
        self.assertEqual(sample.TYPE_GAUGE, delete.type)

    def test_image_size_on_delete(self):
        handler = notifications.ImageSize(mock.Mock())
        counters = list(handler.process_notification(NOTIFICATION_DELETE))
        self.assertEqual(1, len(counters))
        delete = counters[0]
        self._verify_common_counter(delete, 'image.size',
                                    IMAGE_META['size'])
        self.assertEqual(sample.TYPE_GAUGE, delete.type)
