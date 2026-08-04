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
from unittest import mock

import fixtures
import novaclient

from ceilometer import nova_client
from ceilometer import service
from ceilometer.tests import base
from ceilometer.tests.unit import fakes


class TestNovaClient(base.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.CONF = service.prepare_service([], [])
        self.mock_get_session = self.useFixture(fixtures.MockPatch(
            'ceilometer.keystone_client.get_session'))

        self.nv = nova_client.Client(self.CONF)
        self.mock_get_flavor = self.useFixture(fixtures.MockPatchObject(
            self.nv.nova_client.flavors, 'get',
            side_effect=self.fake_flavors_get))

    def setup_connection(self, **kwargs):
        """Override to also update self.nv's client references."""
        super().setup_connection(**kwargs)
        self.nv.image_client = self.fake_conn

    def fake_flavors_get(self, *args, **kwargs):
        a = mock.MagicMock()
        a.id = args[0]
        if a.id == 1:
            a.name = 'm1.tiny'
        elif a.id == 2:
            a.name = 'm1.large'
        else:
            raise novaclient.exceptions.NotFound('foobar')
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
        self.assertEqual({'base_image_ref': 1,
                          'container_format': 'bare',
                          'disk_format': 'qcow2',
                          'min_disk': '1',
                          'min_ram': '0',
                          'os_distro': 'ubuntu',
                          'os_type': 'linux'},
                         instance.image_meta)

    def test_with_flavor_and_image_unknown_image(self):
        instances = self.fake_servers_list_unknown_image()
        results = self.nv._with_flavor_and_image(instances)
        instance = results[0]
        self.assertEqual('unknown-id-666', instance.image['name'])
        self.assertNotEqual(instance.flavor['name'], 'unknown-id-666')
        self.assertIsNone(instance.kernel_id)
        self.assertIsNone(instance.ramdisk_id)
        self.assertEqual({}, instance.image_meta)

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
        self.assertEqual({'base_image_ref': 1,
                          'container_format': 'bare',
                          'disk_format': 'qcow2',
                          'min_disk': '1',
                          'min_ram': '0',
                          'os_distro': 'ubuntu',
                          'os_type': 'linux'},
                         instance.image_meta)

    def test_with_flavor_and_image_none_metadata(self):
        self.setup_connection(images=[fakes.IMAGE_MISSING_METADATA])
        instances = self.fake_servers_list_image_missing_metadata(3)
        results = self.nv._with_flavor_and_image(instances)
        instance = results[0]
        self.assertIsNone(instance.kernel_id)
        self.assertIsNone(instance.ramdisk_id)
        self.assertEqual({'base_image_ref': 3,
                          'container_format': 'bare',
                          'disk_format': 'qcow2',
                          'min_disk': '0',
                          'min_ram': '0'},
                         instance.image_meta)

    def test_with_flavor_and_image_missing_metadata(self):
        self.setup_connection(images=[fakes.IMAGE_MISSING_KERNEL_RAMDISK])
        instances = self.fake_servers_list_image_missing_metadata(4)
        results = self.nv._with_flavor_and_image(instances)
        instance = results[0]
        self.assertIsNone(instance.kernel_id)
        self.assertIsNone(instance.ramdisk_id)
        self.assertEqual({'base_image_ref': 4,
                          'container_format': 'bare',
                          'disk_format': 'qcow2',
                          'min_disk': '0',
                          'min_ram': '0'},
                         instance.image_meta)

    def test_with_flavor_and_image_missing_ramdisk(self):
        self.setup_connection(images=[fakes.IMAGE_MISSING_RAMDISK])
        instances = self.fake_servers_list_image_missing_metadata(5)
        results = self.nv._with_flavor_and_image(instances)
        instance = results[0]
        self.assertEqual(11, instance.kernel_id)
        self.assertIsNone(instance.ramdisk_id)
        self.assertEqual({'base_image_ref': 5,
                          'container_format': 'bare',
                          'disk_format': 'qcow2',
                          'min_disk': '0',
                          'min_ram': '0'},
                         instance.image_meta)

    def test_with_flavor_and_image_missing_kernel(self):
        self.setup_connection(images=[fakes.IMAGE_MISSING_KERNEL])
        instances = self.fake_servers_list_image_missing_metadata(6)
        results = self.nv._with_flavor_and_image(instances)
        instance = results[0]
        self.assertIsNone(instance.kernel_id)
        self.assertEqual(21, instance.ramdisk_id)
        self.assertEqual({'base_image_ref': 6,
                          'container_format': 'bare',
                          'disk_format': 'qcow2',
                          'min_disk': '0',
                          'min_ram': '0'},
                         instance.image_meta)

    def test_with_flavor_and_image_no_cache(self):
        instances = self.fake_servers_list()
        results = self.nv._with_flavor_and_image(instances)
        self.assertEqual(2, len(results))
        self.assertEqual(2, self.mock_get_flavor.mock.call_count)
        self.assertEqual(2, self.fake_conn.image.get_image.call_count)

    def test_with_flavor_and_image_cache(self):
        instances = self.fake_servers_list() * 2
        results = self.nv._with_flavor_and_image(instances)
        self.assertEqual(4, len(results))
        self.assertEqual(2, self.mock_get_flavor.mock.call_count)
        self.assertEqual(2, self.fake_conn.image.get_image.call_count)

    def test_with_flavor_and_image_unknown_image_cache(self):
        instances = self.fake_servers_list_unknown_image() * 2

        results = self.nv._with_flavor_and_image(instances)
        self.assertEqual(2, len(results))
        self.assertEqual(1, self.mock_get_flavor.mock.call_count)
        self.assertEqual(1, self.fake_conn.image.get_image.call_count)
        for instance in results:
            self.assertEqual('unknown-id-666', instance.image['name'])
            self.assertNotEqual(instance.flavor['name'], 'unknown-id-666')
            self.assertIsNone(instance.kernel_id)
            self.assertIsNone(instance.ramdisk_id)
            self.assertEqual({}, instance.image_meta)

    def test_with_image_tags_excluded(self):
        instances = self.fake_servers_list_image_missing_metadata(
            fakes.IMAGE_AMPHORA.id)
        results = self.nv._with_flavor_and_image(instances)
        instance = results[0]
        self.assertNotIn('tags', instance.image_meta)

    def test_with_missing_image_instance(self):
        instances = self.fake_instance_image_missing()
        results = self.nv._with_flavor_and_image(instances)
        instance = results[0]
        self.assertIsNone(instance.kernel_id)
        self.assertIsNone(instance.image)
        self.assertIsNone(instance.ramdisk_id)
