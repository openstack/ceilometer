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

import mock

from ceilometer.compute import manager
from ceilometer.compute.pollsters import disk
from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.tests.compute.pollsters import base


class TestDiskPollsters(base.TestPollsterBase):

    DISKS = [
        (virt_inspector.Disk(device='vda'),
         virt_inspector.DiskStats(read_bytes=1L, read_requests=2L,
                                  write_bytes=3L, write_requests=4L,
                                  errors=-1L))
    ]

    def setUp(self):
        super(TestDiskPollsters, self).setUp()
        self.inspector.inspect_disks = mock.Mock(return_value=self.DISKS)

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def _check_get_samples(self, factory, name, expected_volume):
        pollster = factory()

        mgr = manager.AgentManager()
        cache = {}
        samples = list(pollster.get_samples(mgr, cache, [self.instance]))
        assert samples
        self.assertIn(pollster.CACHE_KEY_DISK, cache)
        self.assertIn(self.instance.name, cache[pollster.CACHE_KEY_DISK])

        self.assertEqual(set([name]), set([s.name for s in samples]))

        match = [s for s in samples if s.name == name]
        self.assertEqual(len(match), 1, 'missing counter %s' % name)
        self.assertEqual(expected_volume, match[0].volume)
        self.assertEqual('cumulative', match[0].type)

    def test_disk_read_requests(self):
        self._check_get_samples(disk.ReadRequestsPollster,
                                'disk.read.requests', 2L)

    def test_disk_read_bytes(self):
        self._check_get_samples(disk.ReadBytesPollster,
                                'disk.read.bytes', 1L)

    def test_disk_write_requests(self):
        self._check_get_samples(disk.WriteRequestsPollster,
                                'disk.write.requests', 4L)

    def test_disk_write_bytes(self):
        self._check_get_samples(disk.WriteBytesPollster,
                                'disk.write.bytes', 3L)


class TestDiskRatePollsters(base.TestPollsterBase):

    DISKS = [
        (virt_inspector.Disk(device='disk1'),
         virt_inspector.DiskRateStats(1024, 300, 5120, 700)),

        (virt_inspector.Disk(device='disk2'),
         virt_inspector.DiskRateStats(2048, 400, 6144, 800))
    ]

    def setUp(self):
        super(TestDiskRatePollsters, self).setUp()
        self.inspector.inspect_disk_rates = \
            mock.Mock(return_value=self.DISKS)

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def _check_get_samples(self, factory, sample_name, expected_volume):
        pollster = factory()

        mgr = manager.AgentManager()
        cache = {}
        samples = list(pollster.get_samples(mgr, cache, [self.instance]))
        assert samples
        self.assertIsNotNone(samples)
        self.assertIn(pollster.CACHE_KEY_DISK_RATE, cache)
        self.assertIn(self.instance.id, cache[pollster.CACHE_KEY_DISK_RATE])

        self.assertEqual(set([sample_name]), set([s.name for s in samples]))

        match = [s for s in samples if s.name == sample_name]
        self.assertEqual(1, len(match), 'missing counter %s' % sample_name)
        self.assertEqual(expected_volume, match[0].volume)
        self.assertEqual('gauge', match[0].type)

    def test_disk_read_bytes_rate(self):
        self._check_get_samples(disk.ReadBytesRatePollster,
                                'disk.read.bytes.rate', 3072L)

    def test_disk_read_requests_rate(self):
        self._check_get_samples(disk.ReadRequestsRatePollster,
                                'disk.read.requests.rate', 700L)

    def test_disk_write_bytes_rate(self):
        self._check_get_samples(disk.WriteBytesRatePollster,
                                'disk.write.bytes.rate', 11264L)

    def test_disk_write_requests_rate(self):
        self._check_get_samples(disk.WriteRequestsRatePollster,
                                'disk.write.requests.rate', 1500L)
