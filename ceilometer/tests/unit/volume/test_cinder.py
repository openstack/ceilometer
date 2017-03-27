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

import mock

from ceilometer.agent import manager
from ceilometer import service
import ceilometer.tests.base as base
from ceilometer.volume import cinder

VOLUME_LIST = [
    type('Volume', (object,),
         {u'migration_status': None,
          u'attachments': [
              {u'server_id': u'1ae69721-d071-4156-a2bd-b11bb43ec2e3',
               u'attachment_id': u'f903d95e-f999-4a34-8be7-119eadd9bb4f',
               u'attached_at': u'2016-07-14T03:55:57.000000',
               u'host_name': None,
               u'volume_id': u'd94c18fb-b680-4912-9741-da69ee83c94f',
               u'device': u'/dev/vdb',
               u'id': u'd94c18fb-b680-4912-9741-da69ee83c94f'}],
          u'links': [{
              u'href': u'http://fake_link3',
              u'rel': u'self'},
              {
                  u'href': u'http://fake_link4',
                  u'rel': u'bookmark'}],
          u'availability_zone': u'nova',
          u'os-vol-host-attr:host': u'test@lvmdriver-1#lvmdriver-1',
          u'encrypted': False,
          u'updated_at': u'2016-07-14T03:55:57.000000',
          u'replication_status': u'disabled',
          u'snapshot_id': None,
          u'id': u'd94c18fb-b680-4912-9741-da69ee83c94f',
          u'size': 1,
          u'user_id': u'be255bd31eb944578000fc762fde6dcf',
          u'os-vol-tenant-attr:tenant_id': u'6824974c08974d4db864bbaa6bc08303',
          u'os-vol-mig-status-attr:migstat': None,
          u'metadata': {u'readonly': u'False', u'attached_mode': u'rw'},
          u'status': u'in-use',
          u'description': None,
          u'multiattach': False,
          u'source_volid': None,
          u'consistencygroup_id': None,
          u'os-vol-mig-status-attr:name_id': None,
          u'name': None,
          u'bootable': u'false',
          u'created_at': u'2016-06-23T08:27:45.000000',
          u'volume_type': u'lvmdriver-1'})
]

SNAPSHOT_LIST = [
    type('VolumeSnapshot', (object,),
         {u'status': u'available',
          u'os-extended-snapshot-attributes:progress': u'100%',
          u'description': None,
          u'os-extended-snapshot-attributes:project_id':
              u'6824974c08974d4db864bbaa6bc08303',
          u'size': 1,
          u'updated_at': u'2016-10-19T07:56:55.000000',
          u'id': u'b1ea6783-f952-491e-a4ed-23a6a562e1cf',
          u'volume_id': u'6f27bc42-c834-49ea-ae75-8d1073b37806',
          u'metadata': {},
          u'created_at': u'2016-10-19T07:56:55.000000',
          u'name': None})
]

BACKUP_LIST = [
    type('VolumeBackup', (object,),
         {u'status': u'available',
          u'object_count': 0,
          u'container': None,
          u'name': None,
          u'links': [{
              u'href': u'http://fake_urla',
              u'rel': u'self'}, {
              u'href': u'http://fake_urlb',
              u'rel': u'bookmark'}],
          u'availability_zone': u'nova',
          u'created_at': u'2016-10-19T06:55:23.000000',
          u'snapshot_id': None,
          u'updated_at': u'2016-10-19T06:55:23.000000',
          u'data_timestamp': u'2016-10-19T06:55:23.000000',
          u'description': None,
          u'has_dependent_backups': False,
          u'volume_id': u'6f27bc42-c834-49ea-ae75-8d1073b37806',
          u'os-backup-project-attr:project_id':
              u'6824974c08974d4db864bbaa6bc08303',
          u'fail_reason': u"",
          u'is_incremental': False,
          u'id': u'75a52125-85ff-4a8d-b2aa-580f3b22273f',
          u'size': 1})
]


class TestVolumeSizePollster(base.BaseTestCase):
    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
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


class TestVolumeSnapshotSizePollster(base.BaseTestCase):
    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
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
        self.assertEqual('6824974c08974d4db864bbaa6bc08303',
                         volume_snapshot_size_samples[0].project_id)
        self.assertEqual('b1ea6783-f952-491e-a4ed-23a6a562e1cf',
                         volume_snapshot_size_samples[0].resource_id)


class TestVolumeBackupSizePollster(base.BaseTestCase):
    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
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
