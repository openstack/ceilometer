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

from ceilometer.agent import plugin_base
from ceilometer import sample


class _Base(plugin_base.PollsterBase):
    @property
    def default_discovery(self):
        return 'images'

    @staticmethod
    def extract_image_metadata(image):
        return dict((k, getattr(image, k))
                    for k in
                    [
                        "status",
                        "visibility",
                        "name",
                        "container_format",
                        "created_at",
                        "disk_format",
                        "updated_at",
                        "min_disk",
                        "protected",
                        "checksum",
                        "min_ram",
                        "tags",
                        "virtual_size"])


class ImageSizePollster(_Base):
    def get_samples(self, manager, cache, resources):
        for image in resources:
            yield sample.Sample(
                name='image.size',
                type=sample.TYPE_GAUGE,
                unit='B',
                volume=image.size,
                user_id=None,
                project_id=image.owner,
                resource_id=image.id,
                resource_metadata=self.extract_image_metadata(image),
            )
