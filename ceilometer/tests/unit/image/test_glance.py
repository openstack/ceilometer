#
# Copyright 2012 New Dream Network, LLC (DreamHost)
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

from ceilometer.agent import manager
from ceilometer.image import glance
from ceilometer import service
import ceilometer.tests.base as base

IMAGE_LIST = [
    type('Image', (object,),
         {u'status': u'active',
          u'tags': [],
          u'kernel_id': u'fd24d91a-dfd5-4a3c-b990-d4563eb27396',
          u'container_format': u'ami',
          u'min_ram': 0,
          u'ramdisk_id': u'd629522b-ebaa-4c92-9514-9e31fe760d18',
          u'updated_at': u'2016-06-20T13: 34: 41Z',
          u'visibility': u'public',
          u'owner': u'6824974c08974d4db864bbaa6bc08303',
          u'file': u'/v2/images/fda54a44-3f96-40bf-ab07-0a4ce9e1761d/file',
          u'min_disk': 0,
          u'virtual_size': None,
          u'id': u'fda54a44-3f96-40bf-ab07-0a4ce9e1761d',
          u'size': 25165824,
          u'name': u'cirros-0.3.4-x86_64-uec',
          u'checksum': u'eb9139e4942121f22bbc2afc0400b2a4',
          u'created_at': u'2016-06-20T13: 34: 40Z',
          u'disk_format': u'ami',
          u'protected': False,
          u'schema': u'/v2/schemas/image'}),
    type('Image', (object,),
         {u'status': u'active',
          u'tags': [],
          u'container_format': u'ari',
          u'min_ram': 0,
          u'updated_at': u'2016-06-20T13: 34: 38Z',
          u'visibility': u'public',
          u'owner': u'6824974c08974d4db864bbaa6bc08303',
          u'file': u'/v2/images/d629522b-ebaa-4c92-9514-9e31fe760d18/file',
          u'min_disk': 0,
          u'virtual_size': None,
          u'id': u'd629522b-ebaa-4c92-9514-9e31fe760d18',
          u'size': 3740163,
          u'name': u'cirros-0.3.4-x86_64-uec-ramdisk',
          u'checksum': u'be575a2b939972276ef675752936977f',
          u'created_at': u'2016-06-20T13: 34: 37Z',
          u'disk_format': u'ari',
          u'protected': False,
          u'schema': u'/v2/schemas/image'}),
    type('Image', (object,),
         {u'status': u'active',
          u'tags': [],
          u'container_format': u'aki',
          u'min_ram': 0,
          u'updated_at': u'2016-06-20T13: 34: 35Z',
          u'visibility': u'public',
          u'owner': u'6824974c08974d4db864bbaa6bc08303',
          u'file': u'/v2/images/fd24d91a-dfd5-4a3c-b990-d4563eb27396/file',
          u'min_disk': 0,
          u'virtual_size': None,
          u'id': u'fd24d91a-dfd5-4a3c-b990-d4563eb27396',
          u'size': 4979632,
          u'name': u'cirros-0.3.4-x86_64-uec-kernel',
          u'checksum': u'8a40c862b5735975d82605c1dd395796',
          u'created_at': u'2016-06-20T13: 34: 35Z',
          u'disk_format': u'aki',
          u'protected': False,
          u'schema': u'/v2/schemas/image'}),
]


class TestImagePollsterPageSize(base.BaseTestCase):
    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(TestImagePollsterPageSize, self).setUp()
        conf = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, conf)
        self.pollster = glance.ImageSizePollster(conf)

    def test_image_pollster(self):
        image_samples = list(
            self.pollster.get_samples(self.manager, {}, resources=IMAGE_LIST))
        self.assertEqual(3, len(image_samples))
        self.assertEqual('image.size', image_samples[0].name)
        self.assertEqual(25165824, image_samples[0].volume)
        self.assertEqual('6824974c08974d4db864bbaa6bc08303',
                         image_samples[0].project_id)
        self.assertEqual('fda54a44-3f96-40bf-ab07-0a4ce9e1761d',
                         image_samples[0].resource_id)
