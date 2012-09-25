# -*- encoding: utf-8 -*-
#
# Copyright © 2012 New Dream Network, LLC (DreamHost)
#
# Author: Doug Hellmann <doug.hellmann@dreamhost.com>
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
"""Common code for working with instances
"""

INSTANCE_PROPERTIES = [
    # Identity properties
    'display_name',
    'reservation_id',
    # Type properties
    'architecture',
    # Location properties
    'availability_zone',
    # Image properties
    'image_ref',
    'image_ref_url',
    'kernel_id',
    'os_type',
    'ramdisk_id',
    # Capacity properties
    'disk_gb',
    'ephemeral_gb',
    'memory_mb',
    'root_gb',
    'vcpus',
    ]


def get_metadata_from_dbobject(instance):
    """Return a metadata dictionary for the instance.
    """
    metadata = {
        'display_name': instance.display_name,
        'instance_type': (instance.instance_type.flavorid
                          if instance.instance_type
                          else None),
        'host': instance.host,
        }
    for name in INSTANCE_PROPERTIES:
        metadata[name] = instance.get(name, u'')
    return metadata
