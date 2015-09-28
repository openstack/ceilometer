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
from oslo_config import fixture as fixture_config
from oslo_context import context
from oslotest import base
from oslotest import mockpatch

from ceilometer.agent import manager
from ceilometer.image import glance

IMAGE_LIST = [
    type('Image', (object,),
         {u'status': u'queued',
          u'name': "some name",
          u'deleted': False,
          u'container_format': None,
          u'created_at': u'2012-09-18T16:29:46',
          u'disk_format': None,
          u'updated_at': u'2012-09-18T16:29:46',
          u'properties': {},
          u'min_disk': 0,
          u'protected': False,
          u'id': u'1d21a8d0-25f4-4e0a-b4ec-85f40237676b',
          u'location': None,
          u'checksum': None,
          u'owner': u'4c8364fc20184ed7971b76602aa96184',
          u'is_public': True,
          u'deleted_at': None,
          u'min_ram': 0,
          u'size': 2048}),
    type('Image', (object,),
         {u'status': u'active',
          u'name': "hello world",
          u'deleted': False,
          u'container_format': None,
          u'created_at': u'2012-09-18T16:27:41',
          u'disk_format': None,
          u'updated_at': u'2012-09-18T16:27:41',
          u'properties': {},
          u'min_disk': 0,
          u'protected': False,
          u'id': u'22be9f90-864d-494c-aa74-8035fd535989',
          u'location': None,
          u'checksum': None,
          u'owner': u'9e4f98287a0246daa42eaf4025db99d4',
          u'is_public': True,
          u'deleted_at': None,
          u'min_ram': 0,
          u'size': 0}),
    type('Image', (object,),
         {u'status': u'queued',
          u'name': None,
          u'deleted': False,
          u'container_format': None,
          u'created_at': u'2012-09-18T16:23:27',
          u'disk_format': "raw",
          u'updated_at': u'2012-09-18T16:23:27',
          u'properties': {},
          u'min_disk': 0,
          u'protected': False,
          u'id': u'8d133f6c-38a8-403c-b02c-7071b69b432d',
          u'location': None,
          u'checksum': None,
          u'owner': u'5f8806a76aa34ee8b8fc8397bd154319',
          u'is_public': True,
          u'deleted_at': None,
          u'min_ram': 0,
          u'size': 1024}),
    type('Image', (object,),
         {u'status': u'queued',
          u'name': "some name",
          u'deleted': False,
          u'container_format': None,
          u'created_at': u'2012-09-18T16:29:46',
          u'disk_format': None,
          u'updated_at': u'2012-09-18T16:29:46',
          u'properties': {},
          u'min_disk': 0,
          u'protected': False,
          u'id': u'e753b196-49b4-48e8-8ca5-09ebd9805f40',
          u'location': None,
          u'checksum': None,
          u'owner': u'4c8364fc20184ed7971b76602aa96184',
          u'is_public': True,
          u'deleted_at': None,
          u'min_ram': 0,
          u'size': 2048}),
]

ENDPOINT = 'end://point'


class _BaseObject(object):
    pass


class FakeGlanceClient(object):
    class images(object):
        pass


class TestManager(manager.AgentManager):

    def __init__(self):
        super(TestManager, self).__init__()
        self._keystone = mock.Mock()
        access = self._keystone.session.auth.get_access.return_value
        access.service_catalog.get_endpoints = mock.Mock(
            return_value={'image': mock.ANY})


class TestImagePollsterPageSize(base.BaseTestCase):

    @staticmethod
    def fake_get_glance_client(ksclient, endpoint):
        glanceclient = FakeGlanceClient()
        glanceclient.images.list = mock.MagicMock(return_value=IMAGE_LIST)
        return glanceclient

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(TestImagePollsterPageSize, self).setUp()
        self.context = context.get_admin_context()
        self.manager = TestManager()
        self.useFixture(mockpatch.PatchObject(
            glance._Base, 'get_glance_client',
            side_effect=self.fake_get_glance_client))
        self.CONF = self.useFixture(fixture_config.Config()).conf

    def _do_test_iter_images(self, page_size=0, length=0):
        self.CONF.set_override("glance_page_size", page_size)
        images = list(glance.ImagePollster().
                      _iter_images(self.manager.keystone, {}, ENDPOINT))
        kwargs = {}
        if page_size > 0:
            kwargs['page_size'] = page_size
        FakeGlanceClient.images.list.assert_called_with(
            filters={'is_public': None}, **kwargs)
        self.assertEqual(length, len(images))

    def test_page_size(self):
        self._do_test_iter_images(100, 4)

    def test_page_size_default(self):
        self._do_test_iter_images(length=4)

    def test_page_size_negative_number(self):
        self._do_test_iter_images(-1, 4)


class TestImagePollster(base.BaseTestCase):

    @staticmethod
    def fake_get_glance_client(ksclient, endpoint):
        glanceclient = _BaseObject()
        setattr(glanceclient, "images", _BaseObject())
        setattr(glanceclient.images,
                "list", lambda *args, **kwargs: iter(IMAGE_LIST))
        return glanceclient

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(TestImagePollster, self).setUp()
        self.context = context.get_admin_context()
        self.manager = TestManager()
        self.useFixture(mockpatch.PatchObject(
            glance._Base, 'get_glance_client',
            side_effect=self.fake_get_glance_client))

    def test_default_discovery(self):
        pollster = glance.ImagePollster()
        self.assertEqual('endpoint:image', pollster.default_discovery)

    def test_iter_images(self):
        # Tests whether the iter_images method returns a unique image
        # list when there is nothing in the cache
        images = list(glance.ImagePollster().
                      _iter_images(self.manager.keystone, {}, ENDPOINT))
        self.assertEqual(len(set(image.id for image in images)), len(images))

    def test_iter_images_cached(self):
        # Tests whether the iter_images method returns the values from
        # the cache
        cache = {'%s-images' % ENDPOINT: []}
        images = list(glance.ImagePollster().
                      _iter_images(self.manager.keystone, cache,
                                   ENDPOINT))
        self.assertEqual([], images)

    def test_image(self):
        samples = list(glance.ImagePollster().get_samples(self.manager, {},
                                                          [ENDPOINT]))
        self.assertEqual(4, len(samples))
        for sample in samples:
            self.assertEqual(1, sample.volume)

    def test_image_size(self):
        samples = list(glance.ImageSizePollster().get_samples(self.manager,
                                                              {},
                                                              [ENDPOINT]))
        self.assertEqual(4, len(samples))
        for image in IMAGE_LIST:
            self.assertTrue(
                any(map(lambda sample: sample.volume == image.size,
                        samples)))

    def test_image_get_sample_names(self):
        samples = list(glance.ImagePollster().get_samples(self.manager, {},
                                                          [ENDPOINT]))
        self.assertEqual(set(['image']), set([s.name for s in samples]))

    def test_image_size_get_sample_names(self):
        samples = list(glance.ImageSizePollster().get_samples(self.manager,
                                                              {},
                                                              [ENDPOINT]))
        self.assertEqual(set(['image.size']), set([s.name for s in samples]))
