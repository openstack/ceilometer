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
"""Common code for working with images
"""

from __future__ import absolute_import

import glanceclient
from oslo_config import cfg
from oslo_utils import timeutils

from ceilometer.agent import plugin_base
from ceilometer import keystone_client
from ceilometer import sample


OPTS = [
    cfg.IntOpt('glance_page_size',
               default=0,
               help="Number of items to request in "
                    "each paginated Glance API request "
                    "(parameter used by glanceclient). "
                    "If this is less than or equal to 0, "
                    "page size is not specified "
                    "(default value in glanceclient is used)."),
]

SERVICE_OPTS = [
    cfg.StrOpt('glance',
               default='image',
               help='Glance service type.'),
]

cfg.CONF.register_opts(OPTS)
cfg.CONF.register_opts(SERVICE_OPTS, group='service_types')


class _Base(plugin_base.PollsterBase):

    @property
    def default_discovery(self):
        return 'endpoint:%s' % cfg.CONF.service_types.glance

    @staticmethod
    def get_glance_client(ksclient, endpoint):
        # hard-code v1 glance API version selection while v2 API matures
        return glanceclient.Client('1',
                                   session=keystone_client.get_session(),
                                   endpoint=endpoint,
                                   auth=ksclient.session.auth)

    def _get_images(self, ksclient, endpoint):
        client = self.get_glance_client(ksclient, endpoint)
        page_size = cfg.CONF.glance_page_size
        kwargs = {}
        if page_size > 0:
            kwargs['page_size'] = page_size
        return client.images.list(filters={"is_public": None}, **kwargs)

    def _iter_images(self, ksclient, cache, endpoint):
        """Iterate over all images."""
        key = '%s-images' % endpoint
        if key not in cache:
            cache[key] = list(self._get_images(ksclient, endpoint))
        return iter(cache[key])

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
                        "size", ])


class ImagePollster(_Base):
    def get_samples(self, manager, cache, resources):
        for endpoint in resources:
            for image in self._iter_images(manager.keystone, cache, endpoint):
                yield sample.Sample(
                    name='image',
                    type=sample.TYPE_GAUGE,
                    unit='image',
                    volume=1,
                    user_id=None,
                    project_id=image.owner,
                    resource_id=image.id,
                    timestamp=timeutils.utcnow().isoformat(),
                    resource_metadata=self.extract_image_metadata(image),
                )


class ImageSizePollster(_Base):
    def get_samples(self, manager, cache, resources):
        for endpoint in resources:
            for image in self._iter_images(manager.keystone, cache, endpoint):
                yield sample.Sample(
                    name='image.size',
                    type=sample.TYPE_GAUGE,
                    unit='B',
                    volume=image.size,
                    user_id=None,
                    project_id=image.owner,
                    resource_id=image.id,
                    timestamp=timeutils.utcnow().isoformat(),
                    resource_metadata=self.extract_image_metadata(image),
                )
