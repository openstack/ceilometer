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
              'os-vol-host-attr:host',
              'migration_status',
              'attachments',
              'snapshot_id',
              'source_volid']

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

        return metadata

    def get_samples(self, manager, cache, resources):
        for volume in resources:
            yield sample.Sample(
                name='volume.size',
                type=sample.TYPE_GAUGE,
                unit='GB',
                volume=volume.size,
                user_id=volume.user_id,
                project_id=getattr(volume,
                                   'os-vol-tenant-attr:tenant_id'),
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
              'os-extended-snapshot-attributes:progress',
              ]

    def get_samples(self, manager, cache, resources):
        for snapshot in resources:
            yield sample.Sample(
                name='volume.snapshot.size',
                type=sample.TYPE_GAUGE,
                unit='GB',
                volume=snapshot.size,
                user_id=snapshot.user_id,
                project_id=getattr(
                    snapshot,
                    'os-extended-snapshot-attributes:project_id'),
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
                unit='GB',
                volume=backup.size,
                user_id=backup.user_id,
                project_id=getattr(
                    backup, 'os-backup-project-attr:project_id', None),
                resource_id=backup.id,
                resource_metadata=self.extract_metadata(backup),
            )


class _VolumeProviderPoolBase(_Base):
    def extract_metadata(self, obj):
        metadata = super().extract_metadata(obj)
        metadata['pool_name'] = getattr(obj, "pool_name", None)
        return metadata


class VolumeProviderPoolCapacityTotal(_VolumeProviderPoolBase):
    @property
    def default_discovery(self):
        return 'volume_pools'

    def get_samples(self, manager, cache, resources):
        for pool in resources:
            yield sample.Sample(
                name='volume.provider.pool.capacity.total',
                type=sample.TYPE_GAUGE,
                unit='GB',
                volume=pool.total_capacity_gb,
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
            yield sample.Sample(
                name='volume.provider.pool.capacity.free',
                type=sample.TYPE_GAUGE,
                unit='GB',
                volume=pool.free_capacity_gb,
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
            if getattr(pool, 'provisioned_capacity_gb', None):
                yield sample.Sample(
                    name='volume.provider.pool.capacity.provisioned',
                    type=sample.TYPE_GAUGE,
                    unit='GB',
                    volume=pool.provisioned_capacity_gb,
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
            if getattr(pool, 'provisioned_capacity_gb', None):
                reserved_size = math.floor(
                    (pool.reserved_percentage / 100) * pool.total_capacity_gb
                )
                max_over_subscription_ratio = 1.0
                if pool.thin_provisioning_support:
                    max_over_subscription_ratio = float(
                        pool.max_over_subscription_ratio
                    )
                value = (
                    max_over_subscription_ratio *
                    (pool.total_capacity_gb - reserved_size) -
                    pool.provisioned_capacity_gb
                )
                yield sample.Sample(
                    name='volume.provider.pool.capacity.virtual_free',
                    type=sample.TYPE_GAUGE,
                    unit='GB',
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
            yield sample.Sample(
                name='volume.provider.pool.capacity.allocated',
                type=sample.TYPE_GAUGE,
                unit='GB',
                volume=pool.allocated_capacity_gb,
                user_id=None,
                project_id=None,
                resource_id=pool.name,
                resource_metadata=self.extract_metadata(pool)
            )
