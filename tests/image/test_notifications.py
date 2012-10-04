# -*- encoding: utf-8 -*-
#
# Copyright © 2012 Red Hat Inc.
#
# Author: Eoghan Glynn <eglynn@redhat.com>
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

from datetime import datetime
import unittest

from ceilometer.image import notifications
from ceilometer import counter
from tests import utils

NOW = datetime.isoformat(datetime.utcnow())

NOTIFICATION_IMAGE_SEND = {
    u'event_type': u'image.send',
    u'timestamp': NOW,
    u'message_id': utils.fake_uuid('a'),
    u'priority': u'INFO',
    u'publisher_id': u'images.example.com',
    u'payload': {u'receiver_tenant_id': utils.fake_uuid('b'),
                 u'destination_ip': u'1.2.3.4',
                 u'bytes_sent': 42,
                 u'image_id': utils.fake_uuid('c'),
                 u'receiver_user_id': utils.fake_uuid('d'),
                 u'owner_id': utils.fake_uuid('e')}
}


class TestNotification(unittest.TestCase):

    def _verify_common_counter(self, c, name):
        self.assertFalse(c is None)
        self.assertEqual(c.name, name)
        self.assertEqual(c.type, counter.TYPE_GAUGE)
        self.assertEqual(c.volume, 42)
        self.assertEqual(c.resource_id, utils.fake_uuid('c'))
        self.assertEqual(c.timestamp, NOW)
        metadata = c.resource_metadata
        self.assertEquals(metadata.get('event_type'), u'image.send')
        self.assertEquals(metadata.get('host'), u'images.example.com')
        self.assertEquals(metadata.get('destination_ip'), u'1.2.3.4')

    def test_image_download(self):
        handler = notifications.ImageDownload()
        counters = handler.process_notification(NOTIFICATION_IMAGE_SEND)
        self.assertEqual(len(counters), 1)
        download = counters[0]
        self._verify_common_counter(download, 'image_download')
        self.assertEqual(download.user_id, utils.fake_uuid('d'))
        self.assertEqual(download.project_id, utils.fake_uuid('b'))
        self.assertEquals(download.resource_metadata.get('owner_id'),
                          utils.fake_uuid('e'))

    def test_image_serve(self):
        handler = notifications.ImageServe()
        counters = handler.process_notification(NOTIFICATION_IMAGE_SEND)
        self.assertEqual(len(counters), 1)
        serve = counters[0]
        self._verify_common_counter(serve, 'image_serve')
        self.assertEqual(serve.user_id, utils.fake_uuid('e'))
        self.assertEquals(serve.resource_metadata.get('receiver_user_id'),
                          utils.fake_uuid('d'))
        self.assertEquals(serve.resource_metadata.get('receiver_tenant_id'),
                          utils.fake_uuid('b'))
