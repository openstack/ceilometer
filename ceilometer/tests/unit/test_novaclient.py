# Copyright 2013-2014 eNovance <licensing@enovance.com>
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

import fixtures
import glanceclient
import mock
import novaclient
from oslotest import base

from ceilometer import nova_client
from ceilometer import service


class TestNovaClient(base.BaseTestCase):

    def setUp(self):
        super(TestNovaClient, self).setUp()
        self.CONF = service.prepare_service([], [])
        self._flavors_count = 0
        self._images_count = 0
        self.nv = nova_client.Client(self.CONF)
        self.useFixture(fixtures.MockPatchObject(
            self.nv.nova_client.flavors, 'get',
            side_effect=self.fake_flavors_get))
        self.useFixture(fixtures.MockPatchObject(
            self.nv.glance_client.images, 'get',
            side_effect=self.fake_images_get))

    def fake_flavors_get(self, *args, **kwargs):
        self._flavors_count += 1
        a = mock.MagicMock()
        a.id = args[0]
        if a.id == 1:
            a.name = 'm1.tiny'
        elif a.id == 2:
            a.name = 'm1.large'
        else:
            raise novaclient.exceptions.NotFound('foobar')
        return a

    def fake_images_get(self, *args, **kwargs):
        self._images_count += 1
        a = mock.MagicMock()
        a.id = args[0]
        image_details = {
            1: ('ubuntu-12.04-x86', dict(kernel_id=11, ramdisk_id=21)),
            2: ('centos-5.4-x64', dict(kernel_id=12, ramdisk_id=22)),
            3: ('rhel-6-x64', None),
            4: ('rhel-6-x64', dict()),
            5: ('rhel-6-x64', dict(kernel_id=11)),
            6: ('rhel-6-x64', dict(ramdisk_id=21))
        }

        if a.id in image_details:
            a.name = image_details[a.id][0]
            a.metadata = image_details[a.id][1]
        else:
            raise glanceclient.exc.HTTPNotFound('foobar')

        return a

    @staticmethod
    def fake_servers_list(*args, **kwargs):
        a = mock.MagicMock()
        a.id = 42
        a.flavor = {'id': 1}
        a.image = {'id': 1}
        b = mock.MagicMock()
        b.id = 43
        b.flavor = {'id': 2}
        b.image = {'id': 2}
        return [a, b]

    def test_instance_get_all_by_host(self):
        with mock.patch.object(self.nv.nova_client.servers, 'list',
                               side_effect=self.fake_servers_list):
            instances = self.nv.instance_get_all_by_host('foobar')

        self.assertEqual(2, len(instances))
        self.assertEqual('m1.tiny', instances[0].flavor['name'])
        self.assertEqual('ubuntu-12.04-x86', instances[0].image['name'])
        self.assertEqual(11, instances[0].kernel_id)
        self.assertEqual(21, instances[0].ramdisk_id)

    def test_instance_get_all(self):
        with mock.patch.object(self.nv.nova_client.servers, 'list',
                               side_effect=self.fake_servers_list):
            instances = self.nv.instance_get_all()

        self.assertEqual(2, len(instances))
        self.assertEqual(42, instances[0].id)
        self.assertEqual(1, instances[0].flavor['id'])
        self.assertEqual(1, instances[0].image['id'])

    @staticmethod
    def fake_servers_list_unknown_flavor(*args, **kwargs):
        a = mock.MagicMock()
        a.id = 42
        a.flavor = {'id': 666}
        a.image = {'id': 1}
        return [a]

    def test_instance_get_all_by_host_unknown_flavor(self):
        with mock.patch.object(
                self.nv.nova_client.servers, 'list',
                side_effect=self.fake_servers_list_unknown_flavor):
            instances = self.nv.instance_get_all_by_host('foobar')

        self.assertEqual(1, len(instances))
        self.assertEqual('unknown-id-666', instances[0].flavor['name'])

    @staticmethod
    def fake_servers_list_unknown_image(*args, **kwargs):
        a = mock.MagicMock()
        a.id = 42
        a.flavor = {'id': 1}
        a.image = {'id': 666}
        return [a]

    @staticmethod
    def fake_servers_list_image_missing_metadata(*args, **kwargs):
        a = mock.MagicMock()
        a.id = 42
        a.flavor = {'id': 1}
        a.image = {'id': args[0]}
        return [a]

    @staticmethod
    def fake_instance_image_missing(*args, **kwargs):
        a = mock.MagicMock()
        a.id = 42
        a.flavor = {'id': 666}
        a.image = None
        return [a]

    def test_instance_get_all_by_host_unknown_image(self):
        with mock.patch.object(
                self.nv.nova_client.servers, 'list',
                side_effect=self.fake_servers_list_unknown_image):
            instances = self.nv.instance_get_all_by_host('foobar')

        self.assertEqual(1, len(instances))
        self.assertEqual('unknown-id-666', instances[0].image['name'])

    def test_with_flavor_and_image(self):
        results = self.nv._with_flavor_and_image(self.fake_servers_list())
        instance = results[0]
        self.assertEqual(2, len(results))
        self.assertEqual('ubuntu-12.04-x86', instance.image['name'])
        self.assertEqual('m1.tiny', instance.flavor['name'])
        self.assertEqual(11, instance.kernel_id)
        self.assertEqual(21, instance.ramdisk_id)

    def test_with_flavor_and_image_unknown_image(self):
        instances = self.fake_servers_list_unknown_image()
        results = self.nv._with_flavor_and_image(instances)
        instance = results[0]
        self.assertEqual('unknown-id-666', instance.image['name'])
        self.assertNotEqual(instance.flavor['name'], 'unknown-id-666')
        self.assertIsNone(instance.kernel_id)
        self.assertIsNone(instance.ramdisk_id)

    def test_with_flavor_and_image_unknown_flavor(self):
        instances = self.fake_servers_list_unknown_flavor()
        results = self.nv._with_flavor_and_image(instances)
        instance = results[0]
        self.assertEqual('unknown-id-666', instance.flavor['name'])
        self.assertEqual(0, instance.flavor['vcpus'])
        self.assertEqual(0, instance.flavor['ram'])
        self.assertEqual(0, instance.flavor['disk'])
        self.assertNotEqual(instance.image['name'], 'unknown-id-666')
        self.assertEqual(11, instance.kernel_id)
        self.assertEqual(21, instance.ramdisk_id)

    def test_with_flavor_and_image_none_metadata(self):
        instances = self.fake_servers_list_image_missing_metadata(3)
        results = self.nv._with_flavor_and_image(instances)
        instance = results[0]
        self.assertIsNone(instance.kernel_id)
        self.assertIsNone(instance.ramdisk_id)

    def test_with_flavor_and_image_missing_metadata(self):
        instances = self.fake_servers_list_image_missing_metadata(4)
        results = self.nv._with_flavor_and_image(instances)
        instance = results[0]
        self.assertIsNone(instance.kernel_id)
        self.assertIsNone(instance.ramdisk_id)

    def test_with_flavor_and_image_missing_ramdisk(self):
        instances = self.fake_servers_list_image_missing_metadata(5)
        results = self.nv._with_flavor_and_image(instances)
        instance = results[0]
        self.assertEqual(11, instance.kernel_id)
        self.assertIsNone(instance.ramdisk_id)

    def test_with_flavor_and_image_missing_kernel(self):
        instances = self.fake_servers_list_image_missing_metadata(6)
        results = self.nv._with_flavor_and_image(instances)
        instance = results[0]
        self.assertIsNone(instance.kernel_id)
        self.assertEqual(21, instance.ramdisk_id)

    def test_with_flavor_and_image_no_cache(self):
        results = self.nv._with_flavor_and_image(self.fake_servers_list())
        self.assertEqual(2, len(results))
        self.assertEqual(2, self._flavors_count)
        self.assertEqual(2, self._images_count)

    def test_with_flavor_and_image_cache(self):
        results = self.nv._with_flavor_and_image(self.fake_servers_list() * 2)
        self.assertEqual(4, len(results))
        self.assertEqual(2, self._flavors_count)
        self.assertEqual(2, self._images_count)

    def test_with_flavor_and_image_unknown_image_cache(self):
        instances = self.fake_servers_list_unknown_image()
        results = self.nv._with_flavor_and_image(instances * 2)
        self.assertEqual(2, len(results))
        self.assertEqual(1, self._flavors_count)
        self.assertEqual(1, self._images_count)
        for instance in results:
            self.assertEqual('unknown-id-666', instance.image['name'])
            self.assertNotEqual(instance.flavor['name'], 'unknown-id-666')
            self.assertIsNone(instance.kernel_id)
            self.assertIsNone(instance.ramdisk_id)

    def test_with_missing_image_instance(self):
        instances = self.fake_instance_image_missing()
        results = self.nv._with_flavor_and_image(instances)
        instance = results[0]
        self.assertIsNone(instance.kernel_id)
        self.assertIsNone(instance.image)
        self.assertIsNone(instance.ramdisk_id)

    def test_with_nova_http_log_debug(self):
        self.CONF.set_override("nova_http_log_debug", True)
        self.nv = nova_client.Client(self.CONF)
        self.assertIsNotNone(self.nv.nova_client.client.logger)
