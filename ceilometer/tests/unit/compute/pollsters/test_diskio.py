#
# Copyright 2012 eNovance <licensing@enovance.com>
# Copyright 2012 Red Hat, Inc
# Copyright 2014 Cisco Systems, Inc
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

from ceilometer.compute.pollsters import disk
from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.polling import manager
from ceilometer.tests.unit.compute.pollsters import base


class TestBaseDiskIO(base.TestPollsterBase):

    TYPE = 'cumulative'

    def setUp(self):
        super(TestBaseDiskIO, self).setUp()
        self.instance = self._get_fake_instances()

    @staticmethod
    def _get_fake_instances():
        instances = []
        for i in [1, 2]:
            instance = mock.MagicMock()
            instance.name = 'instance-%s' % i
            setattr(instance, 'OS-EXT-SRV-ATTR:instance_name',
                    instance.name)
            instance.id = i
            instance.flavor = {'name': 'm1.small', 'id': 2, 'vcpus': 1,
                               'ram': 512, 'disk': 20, 'ephemeral': 0}
            instance.status = 'active'
            instances.append(instance)
        return instances

    def _check_get_samples(self, factory, name, expected_count=2):
        pollster = factory(self.CONF)

        mgr = manager.AgentManager(0, self.CONF)
        cache = {}
        samples = list(pollster.get_samples(mgr, cache, self.instance))
        self.assertIsNotEmpty(samples)
        cache_key = pollster.inspector_method
        self.assertIn(cache_key, cache)
        for instance in self.instance:
            self.assertIn(instance.id, cache[cache_key])
        self.assertEqual(set([name]), set([s.name for s in samples]))

        match = [s for s in samples if s.name == name]
        self.assertEqual(len(match), expected_count,
                         'missing counter %s' % name)
        return match

    def _check_aggregate_samples(self, factory, name,
                                 expected_volume,
                                 expected_device=None):
        match = self._check_get_samples(factory, name)
        self.assertEqual(expected_volume, match[0].volume)
        self.assertEqual(self.TYPE, match[0].type)
        if expected_device is not None:
            self.assertEqual(set(expected_device),
                             set(match[0].resource_metadata.get('device')))
        instances = [i.id for i in self.instance]
        for m in match:
            self.assertIn(m.resource_id, instances)

    def _check_per_device_samples(self, factory, name,
                                  expected_volume,
                                  expected_device=None):
        match = self._check_get_samples(factory, name, expected_count=4)
        match_dict = {}
        for m in match:
            match_dict[m.resource_id] = m
        for instance in self.instance:
            key = "%s-%s" % (instance.id, expected_device)
            self.assertEqual(expected_volume,
                             match_dict[key].volume)
            self.assertEqual(self.TYPE, match_dict[key].type)

            self.assertEqual(key, match_dict[key].resource_id)


class TestDiskPollsters(TestBaseDiskIO):

    DISKS = [
        virt_inspector.DiskStats(device='vda1',
                                 read_bytes=1, read_requests=2,
                                 write_bytes=3, write_requests=4,
                                 errors=-1,
                                 rd_total_times=100,
                                 wr_total_times=200,),
        virt_inspector.DiskStats(device='vda2',
                                 read_bytes=2, read_requests=3,
                                 write_bytes=5, write_requests=7,
                                 errors=-1,
                                 rd_total_times=300,
                                 wr_total_times=400,),
    ]

    def setUp(self):
        super(TestDiskPollsters, self).setUp()
        self.inspector.inspect_disks = mock.Mock(return_value=self.DISKS)

    def test_per_disk_read_requests(self):
        self._check_per_device_samples(disk.PerDeviceReadRequestsPollster,
                                       'disk.device.read.requests', 2,
                                       'vda1')
        self._check_per_device_samples(disk.PerDeviceReadRequestsPollster,
                                       'disk.device.read.requests', 3,
                                       'vda2')

    def test_per_disk_write_requests(self):
        self._check_per_device_samples(disk.PerDeviceWriteRequestsPollster,
                                       'disk.device.write.requests', 4,
                                       'vda1')
        self._check_per_device_samples(disk.PerDeviceWriteRequestsPollster,
                                       'disk.device.write.requests', 7,
                                       'vda2')

    def test_per_disk_read_bytes(self):
        self._check_per_device_samples(disk.PerDeviceReadBytesPollster,
                                       'disk.device.read.bytes', 1,
                                       'vda1')
        self._check_per_device_samples(disk.PerDeviceReadBytesPollster,
                                       'disk.device.read.bytes', 2,
                                       'vda2')

    def test_per_disk_write_bytes(self):
        self._check_per_device_samples(disk.PerDeviceWriteBytesPollster,
                                       'disk.device.write.bytes', 3,
                                       'vda1')
        self._check_per_device_samples(disk.PerDeviceWriteBytesPollster,
                                       'disk.device.write.bytes', 5,
                                       'vda2')

    def test_per_device_read_latency(self):
        self._check_per_device_samples(
            disk.PerDeviceDiskReadLatencyPollster,
            'disk.device.read.latency', 100, 'vda1')

        self._check_per_device_samples(
            disk.PerDeviceDiskReadLatencyPollster,
            'disk.device.read.latency', 300, 'vda2')

    def test_per_device_write_latency(self):
        self._check_per_device_samples(
            disk.PerDeviceDiskWriteLatencyPollster,
            'disk.device.write.latency', 200, 'vda1')

        self._check_per_device_samples(
            disk.PerDeviceDiskWriteLatencyPollster,
            'disk.device.write.latency', 400, 'vda2')


class TestDiskLatencyPollsters(TestBaseDiskIO):

    DISKS = [
        virt_inspector.DiskLatencyStats("disk1", 1),
        virt_inspector.DiskLatencyStats("disk2", 2)
    ]
    TYPE = 'gauge'

    def setUp(self):
        super(TestDiskLatencyPollsters, self).setUp()
        self.inspector.inspect_disk_latency = mock.Mock(
            return_value=self.DISKS)

    def test_per_device_latency(self):
        self._check_per_device_samples(disk.PerDeviceDiskLatencyPollster,
                                       'disk.device.latency', 1, 'disk1')

        self._check_per_device_samples(disk.PerDeviceDiskLatencyPollster,
                                       'disk.device.latency', 2, 'disk2')


class TestDiskIOPSPollsters(TestBaseDiskIO):

    DISKS = [
        virt_inspector.DiskIOPSStats("disk1", 10),
        virt_inspector.DiskIOPSStats("disk2", 20),
    ]
    TYPE = 'gauge'

    def setUp(self):
        super(TestDiskIOPSPollsters, self).setUp()
        self.inspector.inspect_disk_iops = mock.Mock(return_value=self.DISKS)

    def test_per_device_iops(self):
        self._check_per_device_samples(disk.PerDeviceDiskIOPSPollster,
                                       'disk.device.iops', 10, 'disk1')

        self._check_per_device_samples(disk.PerDeviceDiskIOPSPollster,
                                       'disk.device.iops', 20, 'disk2')


class TestDiskInfoPollsters(TestBaseDiskIO):

    DISKS = [
        virt_inspector.DiskInfo(device="vda1", capacity=3,
                                allocation=2, physical=1),
        virt_inspector.DiskInfo(device="vda2", capacity=4,
                                allocation=3, physical=2),
    ]
    TYPE = 'gauge'

    def setUp(self):
        super(TestDiskInfoPollsters, self).setUp()
        self.inspector.inspect_disk_info = mock.Mock(return_value=self.DISKS)

    def test_per_disk_capacity(self):
        self._check_per_device_samples(disk.PerDeviceCapacityPollster,
                                       'disk.device.capacity', 3,
                                       'vda1')
        self._check_per_device_samples(disk.PerDeviceCapacityPollster,
                                       'disk.device.capacity', 4,
                                       'vda2')

    def test_per_disk_allocation(self):
        self._check_per_device_samples(disk.PerDeviceAllocationPollster,
                                       'disk.device.allocation', 2,
                                       'vda1')
        self._check_per_device_samples(disk.PerDeviceAllocationPollster,
                                       'disk.device.allocation', 3,
                                       'vda2')

    def test_per_disk_physical(self):
        self._check_per_device_samples(disk.PerDevicePhysicalPollster,
                                       'disk.device.usage', 1,
                                       'vda1')
        self._check_per_device_samples(disk.PerDevicePhysicalPollster,
                                       'disk.device.usage', 2,
                                       'vda2')
