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

from . import base


class TestDiskPollsters(base.TestPollsterBase):

    DISKS = [
        (virt_inspector.Disk(device='vda'),
         virt_inspector.DiskStats(read_bytes=1L, read_requests=2L,
                                  write_bytes=3L, write_requests=4L,
                                  errors=-1L))
    ]

    def setUp(self):
        super(TestDiskPollsters, self).setUp()
        self.inspector.inspect_disks(self.instance.name).AndReturn(self.DISKS)
        self.mox.ReplayAll()

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def _check_get_counters(self, factory, name, expected_volume):
        pollster = factory()

        mgr = manager.AgentManager()
        cache = {}
        counters = list(pollster.get_counters(mgr, cache, self.instance))
        assert counters
        assert pollster.CACHE_KEY_DISK in cache
        assert self.instance.name in cache[pollster.CACHE_KEY_DISK]

        self.assertEqual(set([c.name for c in counters]),
                         set([name]))

        match = [c for c in counters if c.name == name]
        self.assertEquals(len(match), 1, 'missing counter %s' % name)
        self.assertEquals(match[0].volume, expected_volume)
        self.assertEquals(match[0].type, 'cumulative')

    def test_disk_read_requests(self):
        self._check_get_counters(disk.ReadRequestsPollster,
                                 'disk.read.requests', 2L)

    def test_disk_read_bytes(self):
        self._check_get_counters(disk.ReadBytesPollster,
                                 'disk.read.bytes', 1L)

    def test_disk_write_requests(self):
        self._check_get_counters(disk.WriteRequestsPollster,
                                 'disk.write.requests', 4L)

    def test_disk_write_bytes(self):
        self._check_get_counters(disk.WriteBytesPollster,
                                 'disk.write.bytes', 3L)
