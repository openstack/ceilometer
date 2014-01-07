#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright © 2013 eNovance <licensing@enovance.com>
#
# Author: Julien Danjou <julien@danjou.info>
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
from mock import patch
import novaclient

from ceilometer import nova_client
from ceilometer.openstack.common.fixture import mockpatch
from ceilometer.openstack.common import test


class TestNovaClient(test.BaseTestCase):

    def setUp(self):
        super(TestNovaClient, self).setUp()
        self.nv = nova_client.Client()
        self.useFixture(mockpatch.PatchObject(
            self.nv.nova_client.flavors, 'get',
            side_effect=self.fake_flavors_get))
        self.useFixture(mockpatch.PatchObject(
            self.nv.nova_client.images, 'get',
            side_effect=self.fake_images_get))

    @staticmethod
    def fake_flavors_get(*args, **kwargs):
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
    def fake_images_get(*args, **kwargs):
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
            raise novaclient.exceptions.NotFound('foobar')

        return a

    @staticmethod
    def fake_flavors_list():
        a = mock.MagicMock()
        a.id = 1
        a.name = 'm1.tiny'
        b = mock.MagicMock()
        b.id = 2
        b.name = 'm1.large'
        return [a, b]

    @staticmethod
    def fake_servers_list(*args, **kwargs):
        a = mock.MagicMock()
        a.id = 42
        a.flavor = {'id': 1}
        a.image = {'id': 1}
        return [a]

    def test_instance_get_all_by_host(self):
        with patch.object(self.nv.nova_client.servers, 'list',
                          side_effect=self.fake_servers_list):
            instances = self.nv.instance_get_all_by_host('foobar')

        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0].flavor['name'], 'm1.tiny')
        self.assertEqual(instances[0].image['name'], 'ubuntu-12.04-x86')
        self.assertEqual(instances[0].kernel_id, 11)
        self.assertEqual(instances[0].ramdisk_id, 21)

    @staticmethod
    def fake_servers_list_unknown_flavor(*args, **kwargs):
        a = mock.MagicMock()
        a.id = 42
        a.flavor = {'id': 666}
        a.image = {'id': 1}
        return [a]

    def test_instance_get_all_by_host_unknown_flavor(self):
        with patch.object(self.nv.nova_client.servers, 'list',
                          side_effect=self.fake_servers_list_unknown_flavor):
            instances = self.nv.instance_get_all_by_host('foobar')

        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0].flavor['name'], 'unknown-id-666')

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
        with patch.object(self.nv.nova_client.servers, 'list',
                          side_effect=self.fake_servers_list_unknown_image):
            instances = self.nv.instance_get_all_by_host('foobar')

        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0].image['name'], 'unknown-id-666')

    def test_with_flavor_and_image(self):
        results = self.nv._with_flavor_and_image(self.fake_servers_list())
        instance = results[0]
        self.assertEqual(instance.image['name'], 'ubuntu-12.04-x86')
        self.assertEqual(instance.flavor['name'], 'm1.tiny')
        self.assertEqual(instance.kernel_id, 11)
        self.assertEqual(instance.ramdisk_id, 21)

    def test_with_flavor_and_image_unknown_image(self):
        instances = self.fake_servers_list_unknown_image()
        results = self.nv._with_flavor_and_image(instances)
        instance = results[0]
        self.assertEqual(instance.image['name'], 'unknown-id-666')
        self.assertNotEqual(instance.flavor['name'], 'unknown-id-666')
        self.assertIsNone(instance.kernel_id)
        self.assertIsNone(instance.ramdisk_id)

    def test_with_flavor_and_image_unknown_flavor(self):
        instances = self.fake_servers_list_unknown_flavor()
        results = self.nv._with_flavor_and_image(instances)
        instance = results[0]
        self.assertEqual(instance.flavor['name'], 'unknown-id-666')
        self.assertEqual(instance.flavor['vcpus'], 0)
        self.assertEqual(instance.flavor['ram'], 0)
        self.assertEqual(instance.flavor['disk'], 0)
        self.assertNotEqual(instance.image['name'], 'unknown-id-666')
        self.assertEqual(instance.kernel_id, 11)
        self.assertEqual(instance.ramdisk_id, 21)

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
        self.assertEqual(instance.kernel_id, 11)
        self.assertIsNone(instance.ramdisk_id)

    def test_with_flavor_and_image_missing_kernel(self):
        instances = self.fake_servers_list_image_missing_metadata(6)
        results = self.nv._with_flavor_and_image(instances)
        instance = results[0]
        self.assertIsNone(instance.kernel_id)
        self.assertEqual(instance.ramdisk_id, 21)

    def test_with_missing_image_instance(self):
        instances = self.fake_instance_image_missing()
        results = self.nv._with_flavor_and_image(instances)
        instance = results[0]
        self.assertIsNone(instance.kernel_id)
        self.assertIsNone(instance.image)
        self.assertIsNone(instance.ramdisk_id)
