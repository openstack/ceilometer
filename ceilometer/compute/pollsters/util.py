#
# Copyright 2012 eNovance <licensing@enovance.com>
# Copyright 2012 Red Hat, Inc
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
from oslo_utils import timeutils

from ceilometer.compute import util as compute_util
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


def _get_metadata_from_object(instance):
    """Return a metadata dictionary for the instance."""
    instance_type = instance.flavor['name'] if instance.flavor else None
    metadata = {
        'display_name': instance.name,
        'name': getattr(instance, 'OS-EXT-SRV-ATTR:instance_name', u''),
        'instance_id': instance.id,
        'instance_type': instance_type,
        'host': instance.hostId,
        'instance_host': getattr(instance, 'OS-EXT-SRV-ATTR:host', u''),
        'flavor': instance.flavor,
        'status': instance.status.lower(),
        'state': getattr(instance, 'OS-EXT-STS:vm_state', u''),
    }

    # Image properties
    if instance.image:
        metadata['image'] = instance.image
        metadata['image_ref'] = instance.image['id']
        # Images that come through the conductor API in the nova notifier
        # plugin will not have links.
        if instance.image.get('links'):
            metadata['image_ref_url'] = instance.image['links'][0]['href']
        else:
            metadata['image_ref_url'] = None
    else:
        metadata['image'] = None
        metadata['image_ref'] = None
        metadata['image_ref_url'] = None

    for name in INSTANCE_PROPERTIES:
        if hasattr(instance, name):
            metadata[name] = getattr(instance, name)

    metadata['vcpus'] = instance.flavor['vcpus']
    metadata['memory_mb'] = instance.flavor['ram']
    metadata['disk_gb'] = instance.flavor['disk']
    metadata['ephemeral_gb'] = instance.flavor['ephemeral']
    metadata['root_gb'] = (int(metadata['disk_gb']) -
                           int(metadata['ephemeral_gb']))

    return compute_util.add_reserved_user_metadata(instance.metadata, metadata)


def make_sample_from_instance(instance, name, type, unit, volume,
                              resource_id=None, additional_metadata=None):
    additional_metadata = additional_metadata or {}
    resource_metadata = _get_metadata_from_object(instance)
    resource_metadata.update(additional_metadata)
    return sample.Sample(
        name=name,
        type=type,
        unit=unit,
        volume=volume,
        user_id=instance.user_id,
        project_id=instance.tenant_id,
        resource_id=resource_id or instance.id,
        timestamp=timeutils.utcnow().isoformat(),
        resource_metadata=resource_metadata,
    )


def instance_name(instance):
    """Shortcut to get instance name."""
    return getattr(instance, 'OS-EXT-SRV-ATTR:instance_name', None)
