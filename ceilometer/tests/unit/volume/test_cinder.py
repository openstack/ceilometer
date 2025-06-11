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
from ceilometer.volume import cinder

VOLUME_LIST = [
    type('Volume', (object,),
         {'migration_status': None,
          'attachments': [
              {'server_id': '1ae69721-d071-4156-a2bd-b11bb43ec2e3',
               'attachment_id': 'f903d95e-f999-4a34-8be7-119eadd9bb4f',
               'attached_at': '2016-07-14T03:55:57.000000',
               'host_name': None,
               'volume_id': 'd94c18fb-b680-4912-9741-da69ee83c94f',
               'device': '/dev/vdb',
               'id': 'd94c18fb-b680-4912-9741-da69ee83c94f'}],
          'links': [{
              'href': 'http://fake_link3',
              'rel': 'self'},
              {
                  'href': 'http://fake_link4',
                  'rel': 'bookmark'}],
          'availability_zone': 'nova',
          'os-vol-host-attr:host': 'test@lvmdriver-1#lvmdriver-1',
          'encrypted': False,
          'updated_at': '2016-07-14T03:55:57.000000',
          'replication_status': 'disabled',
          'snapshot_id': None,
          'id': 'd94c18fb-b680-4912-9741-da69ee83c94f',
          'size': 1,
          'user_id': 'be255bd31eb944578000fc762fde6dcf',
          'os-vol-tenant-attr:tenant_id': '6824974c08974d4db864bbaa6bc08303',
          'os-vol-mig-status-attr:migstat': None,
          'metadata': {'readonly': 'False', 'attached_mode': 'rw'},
          'status': 'in-use',
          'description': None,
          'multiattach': False,
          'source_volid': None,
          'consistencygroup_id': None,
          "volume_image_metadata": {
              "checksum": "17d9daa4fb8e20b0f6b7dec0d46fdddf",
              "container_format": "bare",
              "disk_format": "raw",
              "hw_disk_bus": "scsi",
              "hw_scsi_model": "virtio-scsi",
              "image_id": "f0019ee3-523c-45ab-b0b6-3adc529673e7",
              "image_name": "debian-jessie-scsi",
              "min_disk": "0",
              "min_ram": "0",
              "size": "1572864000"
          },
          'os-vol-mig-status-attr:name_id': None,
          'group_id': None,
          'provider_id': None,
          'shared_targets': False,
          'service_uuid': '2f6b5a18-0cd5-4421-b97e-d2c3e85ed758',
          'cluster_name': None,
          'volume_type_id': '65a9f65a-4696-4435-a09d-bc44d797c529',
          'name': None,
          'bootable': 'false',
          'created_at': '2016-06-23T08:27:45.000000',
          'volume_type': 'lvmdriver-1'})
]

SNAPSHOT_LIST = [
    type('VolumeSnapshot', (object,),
         {'status': 'available',
          'os-extended-snapshot-attributes:progress': '100%',
          'description': None,
          'os-extended-snapshot-attributes:project_id':
              '6824974c08974d4db864bbaa6bc08303',
          'size': 1,
          'user_id': 'be255bd31eb944578000fc762fde6dcf',
          'updated_at': '2016-10-19T07:56:55.000000',
          'id': 'b1ea6783-f952-491e-a4ed-23a6a562e1cf',
          'volume_id': '6f27bc42-c834-49ea-ae75-8d1073b37806',
          'metadata': {},
          'created_at': '2016-10-19T07:56:55.000000',
          "group_snapshot_id": None,
          'name': None})
]

BACKUP_LIST = [
    type('VolumeBackup', (object,),
         {'status': 'available',
          'object_count': 0,
          'container': None,
          'name': None,
          'links': [{
              'href': 'http://fake_urla',
              'rel': 'self'}, {
              'href': 'http://fake_urlb',
              'rel': 'bookmark'}],
          'availability_zone': 'nova',
          'created_at': '2016-10-19T06:55:23.000000',
          'snapshot_id': None,
          'updated_at': '2016-10-19T06:55:23.000000',
          'data_timestamp': '2016-10-19T06:55:23.000000',
          'description': None,
          'has_dependent_backups': False,
          'volume_id': '6f27bc42-c834-49ea-ae75-8d1073b37806',
          'os-backup-project-attr:project_id':
              '6824974c08974d4db864bbaa6bc08303',
          'fail_reason': "",
          'is_incremental': False,
          'metadata': {},
          'user_id': 'be255bd31eb944578000fc762fde6dcf',
          'id': '75a52125-85ff-4a8d-b2aa-580f3b22273f',
          'size': 1})
]

POOL_LIST = [
    type('VolumePool', (object,),
         {'name': 'localhost.localdomain@lvmdriver-1#lvmdriver-1',
          'pool_name': 'lvmdriver-1',
          'total_capacity_gb': 28.5,
          'free_capacity_gb': 28.39,
          'reserved_percentage': 0,
          'location_info':
              'LVMVolumeDriver:localhost.localdomain:stack-volumes:thin:0',
          'QoS_support': False,
          'provisioned_capacity_gb': 4.0,
          'max_over_subscription_ratio': 20.0,
          'thin_provisioning_support': True,
          'thick_provisioning_support': False,
          'total_volumes': 3,
          'filter_function': None,
          'goodness_function': None,
          'multiattach': True,
          'backend_state': 'up',
          'allocated_capacity_gb': 4,
          'cacheable': True,
          'volume_backend_name': 'lvmdriver-1',
          'storage_protocol': 'iSCSI',
          'vendor_name': 'Open Source',
          'driver_version': '3.0.0',
          'timestamp': '2025-03-21T14:19:02.901750'}),
    type('VolumePool', (object,),
         {'name': 'cinder-3ceee-volume-ceph-0@ceph#ceph',
          'vendor_name': 'Open Source',
          'driver_version': '1.3.0',
          'storage_protocol': 'ceph',
          'total_capacity_gb': 85.0,
          'free_capacity_gb': 85.0,
          'reserved_percentage': 0,
          'multiattach': True,
          'thin_provisioning_support': True,
          'max_over_subscription_ratio': '20.0',
          'location_info':
          'ceph:/etc/ceph/ceph.conf:a94b63c4e:openstack:volumes',
          'backend_state': 'up',
          'qos_support': True,
          'volume_backend_name': 'ceph',
          'replication_enabled': False,
          'allocated_capacity_gb': 1,
          'filter_function': None,
          'goodness_function': None,
          'timestamp': '2025-06-09T13:29:43.286226'})
]


class TestVolumeSizePollster(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        conf = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, conf)
        self.pollster = cinder.VolumeSizePollster(conf)

    def test_volume_size_pollster(self):
        volume_size_samples = list(
            self.pollster.get_samples(self.manager, {}, resources=VOLUME_LIST))
        self.assertEqual(1, len(volume_size_samples))
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


class TestVolumeSnapshotSizePollster(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        conf = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, conf)
        self.pollster = cinder.VolumeSnapshotSize(conf)

    def test_volume_snapshot_size_pollster(self):
        volume_snapshot_size_samples = list(
            self.pollster.get_samples(
                self.manager, {}, resources=SNAPSHOT_LIST))
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


class TestVolumeBackupSizePollster(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        conf = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, conf)
        self.pollster = cinder.VolumeBackupSize(conf)

    def test_volume_backup_size_pollster(self):
        volume_backup_size_samples = list(
            self.pollster.get_samples(self.manager, {}, resources=BACKUP_LIST))
        self.assertEqual(1, len(volume_backup_size_samples))
        self.assertEqual('volume.backup.size',
                         volume_backup_size_samples[0].name)
        self.assertEqual(1, volume_backup_size_samples[0].volume)
        self.assertEqual('75a52125-85ff-4a8d-b2aa-580f3b22273f',
                         volume_backup_size_samples[0].resource_id)


class TestVolumeProviderPoolCapacityTotalPollster(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        conf = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, conf)
        self.pollster = cinder.VolumeProviderPoolCapacityTotal(conf)

    def test_volume_provider_pool_capacity_total_pollster(self):
        volume_pool_size_total_samples = list(
            self.pollster.get_samples(self.manager, {}, resources=POOL_LIST))
        self.assertEqual(2, len(volume_pool_size_total_samples))

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


class TestVolumeProviderPoolCapacityFreePollster(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        conf = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, conf)
        self.pollster = cinder.VolumeProviderPoolCapacityFree(conf)

    def test_volume_provider_pool_capacity_free_pollster(self):
        volume_pool_size_free_samples = list(
            self.pollster.get_samples(self.manager, {}, resources=POOL_LIST))
        self.assertEqual(2, len(volume_pool_size_free_samples))

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


class TestVolumeProviderPoolCapacityProvisionedPollster(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        conf = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, conf)
        self.pollster = cinder.VolumeProviderPoolCapacityProvisioned(conf)

    def test_volume_provider_pool_capacity_provisioned_pollster(self):
        volume_pool_size_provisioned_samples = list(
            self.pollster.get_samples(self.manager, {}, resources=POOL_LIST))
        self.assertEqual(1, len(volume_pool_size_provisioned_samples))
        self.assertEqual('volume.provider.pool.capacity.provisioned',
                         volume_pool_size_provisioned_samples[0].name)
        self.assertEqual(4.0, volume_pool_size_provisioned_samples[0].volume)
        self.assertEqual('localhost.localdomain@lvmdriver-1#lvmdriver-1',
                         volume_pool_size_provisioned_samples[0].resource_id)


class TestVolumeProviderPoolCapacityVirtualFreePollster(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        conf = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, conf)
        self.pollster = cinder.VolumeProviderPoolCapacityVirtualFree(conf)

    def test_volume_provider_pool_capacity_virtual_free_pollster(self):
        volume_pool_size_virtual_free_samples = list(
            self.pollster.get_samples(self.manager, {}, resources=POOL_LIST))
        self.assertEqual(1, len(volume_pool_size_virtual_free_samples))
        self.assertEqual('volume.provider.pool.capacity.virtual_free',
                         volume_pool_size_virtual_free_samples[0].name)
        self.assertEqual(566.0,
                         volume_pool_size_virtual_free_samples[0].volume)
        self.assertEqual('localhost.localdomain@lvmdriver-1#lvmdriver-1',
                         volume_pool_size_virtual_free_samples[0].resource_id)


class TestVolumeProviderPoolCapacityAllocatedPollster(base.BaseTestCase):
    def setUp(self):
        super().setUp()
        conf = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, conf)
        self.pollster = cinder.VolumeProviderPoolCapacityAllocated(conf)

    def test_volume_provider_pool_capacity_allocated_pollster(self):
        volume_pool_size_allocated_samples = list(
            self.pollster.get_samples(self.manager, {}, resources=POOL_LIST))
        self.assertEqual(2, len(volume_pool_size_allocated_samples))

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
