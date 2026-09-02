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
"""Common code for working with volumes
"""
import math

from ceilometer.polling import plugin_base
from ceilometer import sample

SERVICE_STATE = {
    'up': 1,
    'down': 0,
}


class _Base(plugin_base.PollsterBase):
    FIELDS = []

    def extract_metadata(self, obj):
        return {k: getattr(obj, k) for k in self.FIELDS}


class VolumeSizePollster(_Base):
    @property
    def default_discovery(self):
        return 'volumes'

    FIELDS = ['name',
              'status',
              'volume_type',
              'volume_type_id',
              'availability_zone',
              'migration_status',
              'attachments',
              'snapshot_id']

    def extract_metadata(self, obj):
        metadata = super().extract_metadata(obj)

        if getattr(obj, "volume_image_metadata", None):
            metadata["image_id"] = obj.volume_image_metadata.get("image_id")
        else:
            metadata["image_id"] = None

        if obj.attachments:
            metadata["instance_id"] = obj.attachments[0]["server_id"]
        else:
            metadata["instance_id"] = None
        # Map SDK attribute names to preserve backward compatibility with
        # cinderclient metadata field names
        metadata["os-vol-host-attr:host"] = getattr(obj, "host")
        metadata["source_volid"] = getattr(obj, "source_volume_id")

        return metadata

    def get_samples(self, manager, cache, resources):
        for volume in resources:
            yield sample.Sample(
                name='volume.size',
                type=sample.TYPE_GAUGE,
                unit='GiB',
                volume=volume.size,
                user_id=volume.user_id,
                project_id=volume.project_id,
                resource_id=volume.id,
                resource_metadata=self.extract_metadata(volume),
            )


class VolumeSnapshotSize(_Base):
    @property
    def default_discovery(self):
        return 'volume_snapshots'

    FIELDS = ['name',
              'volume_id',
              'status',
              'description',
              'metadata',
              ]

    def extract_metadata(self, obj):
        metadata = super().extract_metadata(obj)
        # Map SDK attribute names to preserve backward compatibility with
        # cinderclient metadata field names
        metadata["os-extended-snapshot-attributes:progress"] = obj.progress
        return metadata

    def get_samples(self, manager, cache, resources):
        for snapshot in resources:
            yield sample.Sample(
                name='volume.snapshot.size',
                type=sample.TYPE_GAUGE,
                unit='GiB',
                volume=snapshot.size,
                user_id=snapshot.user_id,
                project_id=snapshot.project_id,
                resource_id=snapshot.id,
                resource_metadata=self.extract_metadata(snapshot),
            )


class VolumeBackupSize(_Base):
    @property
    def default_discovery(self):
        return 'volume_backups'

    FIELDS = ['name',
              'is_incremental',
              'object_count',
              'container',
              'volume_id',
              'status',
              'description']

    def get_samples(self, manager, cache, resources):
        for backup in resources:
            yield sample.Sample(
                name='volume.backup.size',
                type=sample.TYPE_GAUGE,
                unit='GiB',
                volume=backup.size,
                user_id=backup.user_id,
                project_id=backup.project_id,
                resource_id=backup.id,
                resource_metadata=self.extract_metadata(backup),
            )


class _VolumeProviderPoolBase(_Base):
    def extract_metadata(self, obj):
        metadata = super().extract_metadata(obj)
        caps = obj.capabilities or {}
        metadata['pool_name'] = caps.get("pool_name") or None
        # A pool is named "<host>@<backend>#<pool>". The volume_provider_pool
        # resource type in gnocchi_resources.yaml maps its ``provider``
        # attribute from resource_metadata.provider, which the capacity.pool
        # notification meters derive the same way (name_to_id up to '#').
        # Polled samples lacked it, so Gnocchi rejected every one of them
        # with "required key not provided @ data['provider']".
        metadata['provider'] = obj.name.split('#', 1)[0]
        return metadata


class VolumeProviderPoolCapacityTotal(_VolumeProviderPoolBase):
    @property
    def default_discovery(self):
        return 'volume_pools'

    def get_samples(self, manager, cache, resources):
        for pool in resources:
            caps = pool.capabilities
            if caps.get('total_capacity_gb') is not None:
                yield sample.Sample(
                    name='volume.provider.pool.capacity.total',
                    type=sample.TYPE_GAUGE,
                    unit='GiB',
                    volume=caps.get('total_capacity_gb'),
                    user_id=None,
                    project_id=None,
                    resource_id=pool.name,
                    resource_metadata=self.extract_metadata(pool)
                )


class VolumeProviderPoolCapacityFree(_VolumeProviderPoolBase):
    @property
    def default_discovery(self):
        return 'volume_pools'

    def get_samples(self, manager, cache, resources):
        for pool in resources:
            caps = pool.capabilities
            if caps.get('free_capacity_gb') is not None:
                yield sample.Sample(
                    name='volume.provider.pool.capacity.free',
                    type=sample.TYPE_GAUGE,
                    unit='GiB',
                    volume=caps['free_capacity_gb'],
                    user_id=None,
                    project_id=None,
                    resource_id=pool.name,
                    resource_metadata=self.extract_metadata(pool)
                )


class VolumeProviderPoolCapacityProvisioned(_VolumeProviderPoolBase):
    @property
    def default_discovery(self):
        return 'volume_pools'

    def get_samples(self, manager, cache, resources):
        for pool in resources:
            caps = pool.capabilities
            if caps.get('provisioned_capacity_gb'):
                yield sample.Sample(
                    name='volume.provider.pool.capacity.provisioned',
                    type=sample.TYPE_GAUGE,
                    unit='GiB',
                    volume=caps['provisioned_capacity_gb'],
                    user_id=None,
                    project_id=None,
                    resource_id=pool.name,
                    resource_metadata=self.extract_metadata(pool)
                )


class VolumeProviderPoolCapacityVirtualFree(_VolumeProviderPoolBase):
    @property
    def default_discovery(self):
        return 'volume_pools'

    def get_samples(self, manager, cache, resources):
        for pool in resources:
            caps = pool.capabilities or {}
            if caps.get('provisioned_capacity_gb'):
                reserved_size = math.floor(
                    (caps['reserved_percentage'] / 100) *
                    caps['total_capacity_gb']
                )
                max_over_subscription_ratio = 1.0
                if caps['thin_provisioning_support']:
                    max_over_subscription_ratio = float(
                        caps.get('max_over_subscription_ratio', 1.0)
                    )
                value = (
                    max_over_subscription_ratio *
                    (caps['total_capacity_gb'] - reserved_size) -
                    caps['provisioned_capacity_gb']
                )
                yield sample.Sample(
                    name='volume.provider.pool.capacity.virtual_free',
                    type=sample.TYPE_GAUGE,
                    unit='GiB',
                    volume=value,
                    user_id=None,
                    project_id=None,
                    resource_id=pool.name,
                    resource_metadata=self.extract_metadata(pool)
                )


class VolumeProviderPoolCapacityAllocated(_VolumeProviderPoolBase):
    @property
    def default_discovery(self):
        return 'volume_pools'

    def get_samples(self, manager, cache, resources):
        for pool in resources:
            caps = pool.capabilities or {}
            yield sample.Sample(
                name='volume.provider.pool.capacity.allocated',
                type=sample.TYPE_GAUGE,
                unit='GiB',
                volume=caps['allocated_capacity_gb'],
                user_id=None,
                project_id=None,
                resource_id=pool.name,
                resource_metadata=self.extract_metadata(pool)
            )


class VolumeServiceHealthPollster(_Base):
    @property
    def default_discovery(self):
        return 'volume_services'

    FIELDS = ['binary', 'host', 'status']

    def extract_metadata(self, obj):
        metadata = super().extract_metadata(obj)
        # Map SDK attribute names to preserve backward compatibility with
        # cinderclient metadata field names
        metadata['zone'] = getattr(obj, 'availability_zone', None)
        return metadata

    def get_samples(self, manager, cache, resources):
        for svc in resources:
            svc_state = getattr(svc, 'state', '').lower()
            if svc_state not in SERVICE_STATE:
                raise ValueError(
                    f"Unknown service state '{svc_state}' for "
                    f"{svc.binary}@{svc.host}")
            state = SERVICE_STATE[svc_state]
            yield sample.Sample(
                name='volume.service.health',
                type=sample.TYPE_GAUGE,
                unit='health',
                volume=state,
                user_id=None,
                project_id=None,
                resource_id=f'{svc.binary}@{svc.host}',
                resource_metadata=self.extract_metadata(svc),
            )
