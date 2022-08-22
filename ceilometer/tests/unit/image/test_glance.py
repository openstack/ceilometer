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

from ceilometer.image import glance
from ceilometer.polling import manager
from ceilometer import service
import ceilometer.tests.base as base

IMAGE_LIST = [
    type('Image', (object,),
         {'status': 'active',
          'tags': [],
          'kernel_id': 'fd24d91a-dfd5-4a3c-b990-d4563eb27396',
          'container_format': 'ami',
          'min_ram': 0,
          'ramdisk_id': 'd629522b-ebaa-4c92-9514-9e31fe760d18',
          'updated_at': '2016-06-20T13: 34: 41Z',
          'visibility': 'public',
          'owner': '6824974c08974d4db864bbaa6bc08303',
          'file': '/v2/images/fda54a44-3f96-40bf-ab07-0a4ce9e1761d/file',
          'min_disk': 0,
          'virtual_size': None,
          'id': 'fda54a44-3f96-40bf-ab07-0a4ce9e1761d',
          'size': 25165824,
          'name': 'cirros-0.3.4-x86_64-uec',
          'checksum': 'eb9139e4942121f22bbc2afc0400b2a4',
          'created_at': '2016-06-20T13: 34: 40Z',
          'disk_format': 'ami',
          'protected': False,
          'schema': '/v2/schemas/image'}),
    type('Image', (object,),
         {'status': 'active',
          'tags': [],
          'container_format': 'ari',
          'min_ram': 0,
          'updated_at': '2016-06-20T13: 34: 38Z',
          'visibility': 'public',
          'owner': '6824974c08974d4db864bbaa6bc08303',
          'file': '/v2/images/d629522b-ebaa-4c92-9514-9e31fe760d18/file',
          'min_disk': 0,
          'virtual_size': None,
          'id': 'd629522b-ebaa-4c92-9514-9e31fe760d18',
          'size': 3740163,
          'name': 'cirros-0.3.4-x86_64-uec-ramdisk',
          'checksum': 'be575a2b939972276ef675752936977f',
          'created_at': '2016-06-20T13: 34: 37Z',
          'disk_format': 'ari',
          'protected': False,
          'schema': '/v2/schemas/image'}),
    type('Image', (object,),
         {'status': 'active',
          'tags': [],
          'container_format': 'aki',
          'min_ram': 0,
          'updated_at': '2016-06-20T13: 34: 35Z',
          'visibility': 'public',
          'owner': '6824974c08974d4db864bbaa6bc08303',
          'file': '/v2/images/fd24d91a-dfd5-4a3c-b990-d4563eb27396/file',
          'min_disk': 0,
          'virtual_size': None,
          'id': 'fd24d91a-dfd5-4a3c-b990-d4563eb27396',
          'size': 4979632,
          'name': 'cirros-0.3.4-x86_64-uec-kernel',
          'checksum': '8a40c862b5735975d82605c1dd395796',
          'created_at': '2016-06-20T13: 34: 35Z',
          'disk_format': 'aki',
          'protected': False,
          'schema': '/v2/schemas/image'}),
]


class TestImagePollsterPageSize(base.BaseTestCase):
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
