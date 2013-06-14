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
from oslo.config import cfg

OPTS = [
    cfg.ListOpt('reserved_metadata_namespace',
                default=['metering.'],
                help='list of metadata prefixes resevred for metering use',
                ),
    cfg.IntOpt('reserved_metadata_length',
               default=256,
               help='limit on length of reserved metadata values'),
]

cfg.CONF.register_opts(OPTS)

INSTANCE_PROPERTIES = [
    # Identity properties
    'reservation_id',
    # Type properties
    'architecture',
    # Location properties
    'availability_zone',
    'kernel_id',
    'os_type',
    'ramdisk_id',
    # Capacity properties
    'disk_gb',
    'ephemeral_gb',
    'memory_mb',
    'root_gb',
    'vcpus']


def add_reserved_user_metadata(instance, metadata):
    limit = cfg.CONF.reserved_metadata_length
    user_metadata = {}
    for prefix in cfg.CONF.reserved_metadata_namespace:
        md = dict(
            (k[len(prefix):].replace('.', '_'),
             v[:limit] if isinstance(v, basestring) else v)
            for k, v in instance.metadata.items()
            if (k.startswith(prefix) and
                k[len(prefix):].replace('.', '_') not in metadata)
        )
        user_metadata.update(md)
    if user_metadata:
        metadata['user_metadata'] = user_metadata

    return metadata


def get_metadata_from_object(instance):
    """Return a metadata dictionary for the instance.
    """
    metadata = {
        'display_name': instance.name,
        'name': getattr(instance, 'OS-EXT-SRV-ATTR:instance_name', u''),
        'instance_type': (instance.flavor['id'] if instance.flavor else None),
        'host': instance.hostId,
        # Image properties
        'image_ref': (instance.image['id'] if instance.image else None),
    }

    # Images that come through the conductor API in the nova notifier
    # plugin will not have links.
    if instance.image and instance.image.get('links'):
        metadata['image_ref_url'] = instance.image['links'][0]['href']
    else:
        metadata['image_ref_url'] = None

    for name in INSTANCE_PROPERTIES:
        metadata[name] = getattr(instance, name, u'')

    return add_reserved_user_metadata(instance, metadata)
