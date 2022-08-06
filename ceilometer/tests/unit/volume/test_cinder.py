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
          u"volume_image_metadata": {
              u"checksum": u"17d9daa4fb8e20b0f6b7dec0d46fdddf",
              u"container_format": u"bare",
              u"disk_format": u"raw",
              u"hw_disk_bus": u"scsi",
              u"hw_scsi_model": u"virtio-scsi",
              u"image_id": u"f0019ee3-523c-45ab-b0b6-3adc529673e7",
              u"image_name": u"debian-jessie-scsi",
              u"min_disk": u"0",
              u"min_ram": u"0",
              u"size": u"1572864000"
          },
          'os-vol-mig-status-attr:name_id': None,
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
          u"volume_image_metadata": {
              u"checksum": u"17d9daa4fb8e20b0f6b7dec0d46fdddf",
              u"container_format": u"bare",
              u"disk_format": u"raw",
              u"hw_disk_bus": u"scsi",
              u"hw_scsi_model": u"virtio-scsi",
              u"image_id": u"f0019ee3-523c-45ab-b0b6-3adc529673e7",
              u"image_name": u"debian-jessie-scsi",
              u"min_disk": u"0",
              u"min_ram": u"0",
              u"size": u"1572864000"
          },
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
          'fail_reason': u"",
          'is_incremental': False,
          'id': '75a52125-85ff-4a8d-b2aa-580f3b22273f',
          'size': 1})
]


class TestVolumeSizePollster(base.BaseTestCase):
    def setUp(self):
        super(TestVolumeSizePollster, self).setUp()
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
        super(TestVolumeSnapshotSizePollster, self).setUp()
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
        self.assertEqual('f0019ee3-523c-45ab-b0b6-3adc529673e7',
                         volume_snapshot_size_samples[0].resource_metadata
                         ["image_id"])


class TestVolumeBackupSizePollster(base.BaseTestCase):
    def setUp(self):
        super(TestVolumeBackupSizePollster, self).setUp()
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
