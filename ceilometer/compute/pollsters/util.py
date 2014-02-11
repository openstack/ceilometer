# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
# Copyright © 2012 Red Hat, Inc
#
# Author: Julien Danjou <julien@danjou.info>
# Author: Eoghan Glynn <eglynn@redhat.com>
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

from oslo.config import cfg

from ceilometer.openstack.common import timeutils
from ceilometer import sample


INSTANCE_PROPERTIES = [
    # Identity properties
    'reservation_id',
    # Type properties
    'architecture',
    'OS-EXT-AZ:availability_zone',
    'kernel_id',
    'os_type',
    'ramdisk_id',
]

OPTS = [
    cfg.ListOpt('reserved_metadata_namespace',
                default=['metering.'],
                help='List of metadata prefixes reserved for metering use.'),
    cfg.IntOpt('reserved_metadata_length',
               default=256,
               help='Limit on length of reserved metadata values.'),
]

cfg.CONF.register_opts(OPTS)


def _add_reserved_user_metadata(instance, metadata):
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


def _get_metadata_from_object(instance):
    """Return a metadata dictionary for the instance.
    """
    metadata = {
        'display_name': instance.name,
        'name': getattr(instance, 'OS-EXT-SRV-ATTR:instance_name', u''),
        'instance_type': (instance.flavor['id'] if instance.flavor else None),
        'host': instance.hostId,
        'flavor': instance.flavor,
        # Image properties
        'image': instance.image,
        'image_ref': (instance.image['id'] if instance.image else None),
    }

    # Images that come through the conductor API in the nova notifier
    # plugin will not have links.
    if instance.image and instance.image.get('links'):
        metadata['image_ref_url'] = instance.image['links'][0]['href']
    else:
        metadata['image_ref_url'] = None

    for name in INSTANCE_PROPERTIES:
        if hasattr(instance, name):
            metadata[name] = getattr(instance, name)

    metadata['vcpus'] = instance.flavor['vcpus']
    metadata['memory_mb'] = instance.flavor['ram']
    metadata['disk_gb'] = instance.flavor['disk']
    metadata['ephemeral_gb'] = instance.flavor['ephemeral']
    metadata['root_gb'] = int(metadata['disk_gb']) - \
        int(metadata['ephemeral_gb'])

    return _add_reserved_user_metadata(instance, metadata)


def make_sample_from_instance(instance, name, type, unit, volume,
                              additional_metadata={}):
    resource_metadata = _get_metadata_from_object(instance)
    resource_metadata.update(additional_metadata)
    return sample.Sample(
        name=name,
        type=type,
        unit=unit,
        volume=volume,
        user_id=instance.user_id,
        project_id=instance.tenant_id,
        resource_id=instance.id,
        timestamp=timeutils.isotime(),
        resource_metadata=resource_metadata,
    )


def instance_name(instance):
    """Shortcut to get instance name."""
    return getattr(instance, 'OS-EXT-SRV-ATTR:instance_name', None)
