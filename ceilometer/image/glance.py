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

from keystoneclient.v2_0 import client as ksclient
from glance.registry import client

from ceilometer import plugin
from ceilometer.counter import Counter
from ceilometer.openstack.common import cfg
from ceilometer.openstack.common import timeutils

cfg.CONF.register_opts(
    [
        cfg.StrOpt('glance_registry_host',
                   default='localhost',
                   help="URL of Glance API server"),
        cfg.IntOpt('glance_registry_port',
                   default=9191,
                   help="URL of Glance API server"),
    ])


class _Base(plugin.PollsterBase):

    @staticmethod
    def get_registry_client():
        k = ksclient.Client(username=cfg.CONF.os_username,
                            password=cfg.CONF.os_password,
                            tenant_id=cfg.CONF.os_tenant_id,
                            tenant_name=cfg.CONF.os_tenant_name,
                            auth_url=cfg.CONF.os_auth_url)
        return client.RegistryClient(cfg.CONF.glance_registry_host,
                                     cfg.CONF.glance_registry_port,
                                     auth_tok=k.auth_token)

    def iter_images(self):
        """Iterate over all images."""
        # We need to ask for both public and non public to get all images.
        client = self.get_registry_client()
        return itertools.chain(
            client.get_images_detailed(filters={"is_public": True}),
            client.get_images_detailed(filters={"is_public": False}))

    @staticmethod
    def extract_image_metadata(image):
        return dict([(k, image[k])
                     for k in [
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
                             "location",
                             "checksum",
                             "deleted_at",
                             "min_ram",
                             "size",
                     ]
                 ])


class ImagePollster(_Base):

    def get_counters(self, manager, context):
        for image in self.iter_images():
            yield Counter(
                source='?',
                name='image',
                type='absolute',
                volume=1,
                user_id=None,
                project_id=image['owner'],
                resource_id=image['id'],
                timestamp=timeutils.isotime(),
                duration=None,
                resource_metadata=self.extract_image_metadata(image),
            )


class ImageSizePollster(_Base):

    def get_counters(self, manager, context):
        for image in self.iter_images():
            yield Counter(
                source='?',
                name='image_size',
                type='absolute',
                volume=image['size'],
                user_id=None,
                project_id=image['owner'],
                resource_id=image['id'],
                timestamp=timeutils.isotime(),
                duration=None,
                resource_metadata=self.extract_image_metadata(image),
            )
