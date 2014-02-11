# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
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
"""Common code for working with images
"""

from __future__ import absolute_import
import itertools

import glanceclient
from oslo.config import cfg

from ceilometer.openstack.common import timeutils
from ceilometer import plugin
from ceilometer import sample


class _Base(plugin.PollsterBase):

    @staticmethod
    def get_glance_client(ksclient):
        endpoint = ksclient.service_catalog.url_for(
            service_type='image',
            endpoint_type=cfg.CONF.service_credentials.os_endpoint_type)

        # hard-code v1 glance API version selection while v2 API matures
        service_credentials = cfg.CONF.service_credentials
        return glanceclient.Client('1', endpoint,
                                   token=ksclient.auth_token,
                                   cacert=service_credentials.os_cacert,
                                   insecure=service_credentials.insecure)

    def _get_images(self, ksclient):
        client = self.get_glance_client(ksclient)
        #TODO(eglynn): use pagination to protect against unbounded
        #              memory usage
        rawImageList = list(itertools.chain(
            client.images.list(filters={"is_public": True}),
            #TODO(eglynn): extend glance API with all_tenants logic to
            #              avoid second call to retrieve private images
            client.images.list(filters={"is_public": False})))

        # When retrieving images from glance, glance will check
        # whether the user is of 'admin_role' which is
        # configured in glance-api.conf. If the user is of
        # admin_role, and is querying public images(which means
        # that the 'is_public' param is set to be True),
        # glance will ignore 'is_public' parameter and returns
        # all the public images together with private images.
        # As a result, if the user/tenant has an admin role
        # for ceilometer to collect image list,
        # the _Base.iter_images method will return a image list
        # which contains duplicate images. Add the following
        # code to avoid recording down duplicate image events.
        imageIdSet = set(image.id for image in rawImageList)

        for image in rawImageList:
            if image.id in imageIdSet:
                imageIdSet -= set([image.id])
                yield image

    def _iter_images(self, ksclient, cache):
        """Iterate over all images."""
        if 'images' not in cache:
            cache['images'] = list(self._get_images(ksclient))
        return iter(cache['images'])

    @staticmethod
    def extract_image_metadata(image):
        return dict((k, getattr(image, k))
                    for k in
                    [
                        "status",
                        "is_public",
                        "name",
                        "deleted",
                        "container_format",
                        "created_at",
                        "disk_format",
                        "updated_at",
                        "properties",
                        "min_disk",
                        "protected",
                        "checksum",
                        "deleted_at",
                        "min_ram",
                        "size",
                    ])


class ImagePollster(_Base):

    def get_samples(self, manager, cache, resources=[]):
        for image in self._iter_images(manager.keystone, cache):
            yield sample.Sample(
                name='image',
                type=sample.TYPE_GAUGE,
                unit='image',
                volume=1,
                user_id=None,
                project_id=image.owner,
                resource_id=image.id,
                timestamp=timeutils.isotime(),
                resource_metadata=self.extract_image_metadata(image),
            )


class ImageSizePollster(_Base):

    def get_samples(self, manager, cache, resources=[]):
        for image in self._iter_images(manager.keystone, cache):
            yield sample.Sample(
                name='image.size',
                type=sample.TYPE_GAUGE,
                unit='B',
                volume=image.size,
                user_id=None,
                project_id=image.owner,
                resource_id=image.id,
                timestamp=timeutils.isotime(),
                resource_metadata=self.extract_image_metadata(image),
            )
