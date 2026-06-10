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

from ceilometer.polling import manager
from ceilometer import service
import ceilometer.tests.base as base
from ceilometer.tests.unit import fakes
from ceilometer.volume import cinder


class TestVolumeSizePollster(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        conf = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, conf)
        self.pollster = cinder.VolumeSizePollster(conf)

    def test_volume_size_pollster(self):
        volume_size_samples = list(
            self.pollster.get_samples(
                self.manager, {}, resources=fakes.VOLUME_LIST))
        self.assertEqual(len(fakes.VOLUME_LIST), len(volume_size_samples))
        self.assertEqual('volume.size', volume_size_samples[0].name)
        self.assertEqual(1, volume_size_samples[0].volume)
        self.assertEqual('6824974c08974d4db864bbaa6bc08303',
                         volume_size_samples[0].project_id)
        self.assertEqual('d94c18fb-b680-4912-9741-da69ee83c94f',
                         volume_size_samples[0].resource_id)
        self.assertEqual('f0019ee3-523c-45ab-b0b6-3adc529673e7',
                         volume_size_samples[0].resource_metadata["image_id"])
        self.assertEqual('1ae69721-d071-4156-a2bd-b11bb43ec2e3',
                         volume_size_samples[0].resource_metadata
                         ["instance_id"])
        self.assertEqual('nova', volume_size_samples[0].resource_metadata
                         ["availability_zone"])

    def test_get_samples_volume_metadata_contains_expected_fields(self):
        """Test that the expected metadata field exist in the sample.

        Publishers and operators may expect certain metadata to exist.
        """
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=fakes.VOLUME_LIST))
        metadata = samples[0].resource_metadata
        self.assertIn('name', metadata)
        self.assertIn('status', metadata)
        self.assertIn('volume_type', metadata)
        self.assertIn('volume_type_id', metadata)
        self.assertIn('availability_zone', metadata)
        self.assertIn('os-vol-host-attr:host', metadata)
        self.assertIn('attachments', metadata)
        self.assertIn('snapshot_id', metadata)
        self.assertIn('source_volid', metadata)
        self.assertIn('image_id', metadata)
        self.assertIn('instance_id', metadata)


class TestVolumeSnapshotSizePollster(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        conf = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, conf)
        self.pollster = cinder.VolumeSnapshotSize(conf)

    def test_volume_snapshot_size_pollster(self):
        volume_snapshot_size_samples = list(
            self.pollster.get_samples(
                self.manager, {}, resources=fakes.SNAPSHOT_LIST))
        self.assertEqual(1, len(volume_snapshot_size_samples))
        self.assertEqual('volume.snapshot.size',
                         volume_snapshot_size_samples[0].name)
        self.assertEqual(1, volume_snapshot_size_samples[0].volume)
        self.assertEqual('be255bd31eb944578000fc762fde6dcf',
                         volume_snapshot_size_samples[0].user_id)
        self.assertEqual('6824974c08974d4db864bbaa6bc08303',
                         volume_snapshot_size_samples[0].project_id)
        self.assertEqual('b1ea6783-f952-491e-a4ed-23a6a562e1cf',
                         volume_snapshot_size_samples[0].resource_id)

    def test_get_samples_contains_expected_metadata(self):
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=fakes.SNAPSHOT_LIST))
        for s in samples:
            metadata = s.resource_metadata
            self.assertIsNotNone(metadata)
            self.assertIn('name', metadata)
            self.assertIn('volume_id', metadata)
            self.assertIn('status', metadata)
            self.assertIn('description', metadata)
            self.assertIn('metadata', metadata)
            self.assertIn('os-extended-snapshot-attributes:progress', metadata)


class TestVolumeBackupSizePollster(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        conf = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, conf)
        self.pollster = cinder.VolumeBackupSize(conf)

    def test_volume_backup_size_pollster(self):
        volume_backup_size_samples = list(
            self.pollster.get_samples(
                self.manager, {}, resources=fakes.BACKUP_LIST))
        self.assertEqual(1, len(volume_backup_size_samples))
        self.assertEqual('volume.backup.size',
                         volume_backup_size_samples[0].name)
        self.assertEqual(1, volume_backup_size_samples[0].volume)
        self.assertEqual('75a52125-85ff-4a8d-b2aa-580f3b22273f',
                         volume_backup_size_samples[0].resource_id)
        self.assertEqual('6824974c08974d4db864bbaa6bc08303',
                         volume_backup_size_samples[0].project_id)

    def test_get_samples_contains_expected_metadata(self):
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=fakes.BACKUP_LIST))
        for s in samples:
            metadata = s.resource_metadata
            self.assertIsNotNone(metadata)
            self.assertIn('name', metadata)
            self.assertIn('is_incremental', metadata)
            self.assertIn('object_count', metadata)
            self.assertIn('container', metadata)
            self.assertIn('volume_id', metadata)
            self.assertIn('status', metadata)
            self.assertIn('description', metadata)


class TestVolumeProviderPoolCapacityTotalPollster(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        conf = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, conf)
        self.pollster = cinder.VolumeProviderPoolCapacityTotal(conf)

    def test_volume_provider_pool_capacity_total_pollster(self):
        volume_pool_size_total_samples = list(
            self.pollster.get_samples(
                self.manager, {}, resources=fakes.POOL_LIST))
        self.assertEqual(len(fakes.POOL_LIST),
                         len(volume_pool_size_total_samples))

        self.assertEqual('volume.provider.pool.capacity.total',
                         volume_pool_size_total_samples[0].name)
        self.assertEqual(28.5, volume_pool_size_total_samples[0].volume)
        self.assertEqual('localhost.localdomain@lvmdriver-1#lvmdriver-1',
                         volume_pool_size_total_samples[0].resource_id)

        self.assertEqual('volume.provider.pool.capacity.total',
                         volume_pool_size_total_samples[1].name)
        self.assertEqual(85.0, volume_pool_size_total_samples[1].volume)
        self.assertEqual('cinder-3ceee-volume-ceph-0@ceph#ceph',
                         volume_pool_size_total_samples[1].resource_id)

    def test_get_samples_contains_expected_metadata(self):
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=fakes.POOL_LIST))
        for s in samples:
            metadata = s.resource_metadata
            self.assertIsNotNone(metadata)
            self.assertIn('pool_name', metadata)

    def test_get_samples_no_capacity_in_capability_field(self):

        self.assertRaises(
            AttributeError,
            list,
            self.pollster.get_samples(
                self.manager, {}, resources=[fakes.POOL_NO_CAPABILITIES])
        )


class TestVolumeProviderPoolCapacityFreePollster(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        conf = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, conf)
        self.pollster = cinder.VolumeProviderPoolCapacityFree(conf)

    def test_volume_provider_pool_capacity_free_pollster(self):
        volume_pool_size_free_samples = list(
            self.pollster.get_samples(
                self.manager, {}, resources=fakes.POOL_LIST))
        self.assertEqual(len(fakes.POOL_LIST),
                         len(volume_pool_size_free_samples))

        self.assertEqual('volume.provider.pool.capacity.free',
                         volume_pool_size_free_samples[0].name)
        self.assertEqual(28.39, volume_pool_size_free_samples[0].volume)
        self.assertEqual('localhost.localdomain@lvmdriver-1#lvmdriver-1',
                         volume_pool_size_free_samples[0].resource_id)

        self.assertEqual('volume.provider.pool.capacity.free',
                         volume_pool_size_free_samples[1].name)
        self.assertEqual(85.0, volume_pool_size_free_samples[1].volume)
        self.assertEqual('cinder-3ceee-volume-ceph-0@ceph#ceph',
                         volume_pool_size_free_samples[1].resource_id)

    def test_get_samples_contains_expected_metadata(self):
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=fakes.POOL_LIST))
        for s in samples:
            metadata = s.resource_metadata
            self.assertIsNotNone(metadata)
            self.assertIn('pool_name', metadata)

    def test_get_samples_no_free_capacity_gb(self):
        """Test behaviour when required attribute is not present.

        The free_capacity_gb attribute is needed to populate the volume
        of the sample.
        """
        # No pool.free_capacity_gb i.e. the volume for the sample.
        self.assertRaises(
            AttributeError,
            list,
            self.pollster.get_samples(
                self.manager, {}, resources=[fakes.POOL_NO_CAPABILITIES])
        )


class TestVolumeProviderPoolCapacityProvisionedPollster(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        conf = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, conf)
        self.pollster = cinder.VolumeProviderPoolCapacityProvisioned(conf)

    def test_volume_provider_pool_capacity_provisioned_pollster(self):
        volume_pool_size_provisioned_samples = list(
            self.pollster.get_samples(
                self.manager, {}, resources=fakes.POOL_LIST))
        self.assertEqual(1, len(volume_pool_size_provisioned_samples))
        self.assertEqual('volume.provider.pool.capacity.provisioned',
                         volume_pool_size_provisioned_samples[0].name)
        self.assertEqual(4.0, volume_pool_size_provisioned_samples[0].volume)
        self.assertEqual('localhost.localdomain@lvmdriver-1#lvmdriver-1',
                         volume_pool_size_provisioned_samples[0].resource_id)

    def test_get_samples_contains_expected_metadata(self):
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=fakes.POOL_LIST))
        for s in samples:
            metadata = s.resource_metadata
            self.assertIsNotNone(metadata)
            self.assertIn('pool_name', metadata)


class TestVolumeProviderPoolCapacityVirtualFreePollster(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        conf = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, conf)
        self.pollster = cinder.VolumeProviderPoolCapacityVirtualFree(conf)

    def test_volume_provider_pool_capacity_virtual_free_pollster(self):
        volume_pool_size_virtual_free_samples = list(
            self.pollster.get_samples(
                self.manager, {}, resources=fakes.POOL_LIST))
        self.assertEqual(1, len(volume_pool_size_virtual_free_samples))
        self.assertEqual('volume.provider.pool.capacity.virtual_free',
                         volume_pool_size_virtual_free_samples[0].name)
        self.assertEqual(566.0,
                         volume_pool_size_virtual_free_samples[0].volume)
        self.assertEqual('localhost.localdomain@lvmdriver-1#lvmdriver-1',
                         volume_pool_size_virtual_free_samples[0].resource_id)

    def test_get_samples_contains_expected_metadata(self):
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=fakes.POOL_LIST))
        for s in samples:
            metadata = s.resource_metadata
            self.assertIsNotNone(metadata)
            self.assertIn('pool_name', metadata)

    def test_get_samples_missing_provisioned_capacity_skips_pool(self):
        """Verify pools without provisioned_capacity_gb are silently skipped.

        The pollster uses getattr(pool, 'provisioned_capacity_gb', None) as a
        guard, so pools missing this attribute yield no samples.
        """
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=[fakes.POOL_NO_PROVISIONED_CAPACITY]))
        self.assertEqual(0, len(samples))

    def test_get_samples_missing_thin_provisioning_raises_err(self):
        """Verify missing thin_provisioning_support raises AttributeError.

        When provisioned_capacity_gb IS set but thin_provisioning_support is
        missing, the pollster attempts to access the attribute and raises
        AttributeError. This documents current behavior.
        """
        self.assertRaises(
            AttributeError,
            list,
            self.pollster.get_samples(
                self.manager, {},
                resources=[fakes.POOL_NO_THIN_PROVISIONING]))

    def test_get_samples_thick_provisioning_uses_ratio_one(self):
        """Verify thin_provisioning_support=False uses ratio 1.0.

        When thin_provisioning_support is False, max_over_subscription_ratio
        defaults to 1.0, resulting in volume = 1.0 * (28.5 - 0) - 4.0 = 24.5.
        """
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=[fakes.POOL_THICK_PROVISIONING]))
        self.assertEqual(1, len(samples))
        self.assertEqual(24.5, samples[0].volume)

    def test_get_samples_missing_reserved_percentage(self):
        """Verify the behaviour when reserved_percentage is not set.

        Setup: provisioned_capacity_gb set, but reserved_percentage missing
        Expected behaviour: there is an error
        """
        self.assertRaises(AttributeError, list, self.pollster.get_samples(
            self.manager, {}, resources=[fakes.POOL_NO_RESERVED_PERCENTAGE]))


class TestVolumeProviderPoolCapacityAllocatedPollster(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        conf = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, conf)
        self.pollster = cinder.VolumeProviderPoolCapacityAllocated(conf)

    def test_volume_provider_pool_capacity_allocated_pollster(self):
        volume_pool_size_allocated_samples = list(
            self.pollster.get_samples(
                self.manager, {}, resources=fakes.POOL_LIST))
        self.assertEqual(len(fakes.POOL_LIST),
                         len(volume_pool_size_allocated_samples))

        self.assertEqual('volume.provider.pool.capacity.allocated',
                         volume_pool_size_allocated_samples[0].name)
        self.assertEqual(4, volume_pool_size_allocated_samples[0].volume)
        self.assertEqual('localhost.localdomain@lvmdriver-1#lvmdriver-1',
                         volume_pool_size_allocated_samples[0].resource_id)

        self.assertEqual('volume.provider.pool.capacity.allocated',
                         volume_pool_size_allocated_samples[1].name)
        self.assertEqual(1, volume_pool_size_allocated_samples[1].volume)
        self.assertEqual('cinder-3ceee-volume-ceph-0@ceph#ceph',
                         volume_pool_size_allocated_samples[1].resource_id)

    def test_get_samples_contains_expected_metadata(self):
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=fakes.POOL_LIST))
        for s in samples:
            metadata = s.resource_metadata
            self.assertIsNotNone(metadata)
            self.assertIn('pool_name', metadata)

    def test_get_samples_zero_allocated_cap_emits_sample(self):
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=[fakes.POOL_ZERO_ALLOCATED_CAPACITY]))
        self.assertEqual(1, len(samples))
        self.assertEqual(0, samples[0].volume)

    def test_get_samples_missing_allocated_cap_raises_err(self):
        self.assertRaises(
            AttributeError,
            list,
            self.pollster.get_samples(
                self.manager, {},
                resources=[fakes.POOL_NO_CAPABILITIES]))


class TestVolumeServiceHealthPollster(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        conf = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, conf)
        self.pollster = cinder.VolumeServiceHealthPollster(conf)

    def test_volume_service_health_pollster(self):
        samples = list(
            self.pollster.get_samples(
                self.manager, {}, resources=fakes.SERVICE_LIST))
        self.assertEqual(len(fakes.SERVICE_LIST), len(samples))

        self.assertEqual('volume.service.health', samples[0].name)
        self.assertEqual(1, samples[0].volume)
        self.assertEqual('cinder-volume@devstack',
                         samples[0].resource_id)
        self.assertEqual('cinder-volume',
                         samples[0].resource_metadata['binary'])
        self.assertEqual('nova',
                         samples[0].resource_metadata['zone'])

        self.assertEqual('volume.service.health', samples[1].name)
        self.assertEqual(1, samples[1].volume)
        self.assertEqual('cinder-scheduler@devstack',
                         samples[1].resource_id)
        self.assertEqual('cinder-scheduler',
                         samples[1].resource_metadata['binary'])

        self.assertEqual('volume.service.health', samples[2].name)
        self.assertEqual(0, samples[2].volume)
        self.assertEqual('cinder-backup@devstack',
                         samples[2].resource_id)
        self.assertEqual('cinder-backup',
                         samples[2].resource_metadata['binary'])

    def test_get_samples_contains_expected_metadata(self):
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=fakes.SERVICE_LIST))
        for s in samples:
            metadata = s.resource_metadata
            self.assertIsNotNone(metadata)
            self.assertIn('binary', metadata)
            self.assertIn('host', metadata)
            self.assertIn('zone', metadata)
            self.assertIn('status', metadata)

    def test_volume_service_health_unknown_state(self):
        bad_service = [
            type('Service', (object,),
                 {'binary': 'cinder-volume',
                  'host': 'devstack',
                  'zone': 'nova',
                  'status': 'enabled',
                  'state': 'unknown'}),
        ]
        self.assertRaises(
            ValueError,
            list,
            self.pollster.get_samples(
                self.manager, {}, resources=bad_service))
