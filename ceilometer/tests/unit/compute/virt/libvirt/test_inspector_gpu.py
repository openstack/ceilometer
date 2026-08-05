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
"""Tests for GPU inspection in the libvirt inspector."""

from unittest import mock

from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.compute.virt.libvirt import inspector as libvirt_inspector
from ceilometer.compute.virt.libvirt import utils
from ceilometer import service
from ceilometer.tests import base


DOMAIN_XML_ONE_VGPU = """
<domain type='kvm'>
  <devices>
    <hostdev mode='subsystem' type='mdev' managed='no' model='vfio-pci'>
      <source>
        <address uuid='a1b2c3d4-e5f6-7890-abcd-ef1234567890'/>
      </source>
    </hostdev>
  </devices>
</domain>
"""

DOMAIN_XML_TWO_VGPUS = """
<domain type='kvm'>
  <devices>
    <hostdev mode='subsystem' type='mdev' managed='no' model='vfio-pci'>
      <source>
        <address uuid='a1b2c3d4-e5f6-7890-abcd-ef1234567890'/>
      </source>
    </hostdev>
    <hostdev mode='subsystem' type='mdev' managed='no' model='vfio-pci'>
      <source>
        <address uuid='b2c3d4e5-f6a7-8901-bcde-f12345678901'/>
      </source>
    </hostdev>
  </devices>
</domain>
"""

DOMAIN_XML_NO_GPU = """
<domain type='kvm'>
  <devices>
    <disk type='file' device='disk'>
      <source file='/var/lib/nova/instances/test/disk'/>
      <target dev='vda' bus='virtio'/>
    </disk>
  </devices>
</domain>
"""


class FakeLibvirtError(Exception):
    pass


class FakeNVMLError(Exception):
    pass


class VMInstance:
    id = 'ff58e738-12f4-4c58-acde-77617b68da56'
    name = 'instance-00000001'


class TestLibvirtInspectorGPU(base.BaseTestCase):

    def setUp(self):
        super().setUp()
        conf = service.prepare_service([], [])

        self.instance = VMInstance()
        libvirt_inspector.libvirt = mock.Mock()
        libvirt_inspector.libvirt.getVersion.return_value = 5001001
        libvirt_inspector.libvirt.VIR_DOMAIN_SHUTOFF = 5
        libvirt_inspector.libvirt.libvirtError = FakeLibvirtError
        utils.libvirt = libvirt_inspector.libvirt

        self.mock_pynvml = mock.MagicMock()
        self.mock_pynvml.NVMLError = FakeNVMLError

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=None):
            with mock.patch.object(libvirt_inspector, 'pynvml',
                                   self.mock_pynvml):
                self.inspector = libvirt_inspector.LibvirtInspector(conf)
                self.inspector._nvml_available = \
                    libvirt_inspector._NVML_UNCHECKED

    def _setup_nvml_mocks(self, gpu_count=1, vgpu_uuids=None,
                          mdev_uuids=None):
        """Set up NVML mocks for a typical GPU scenario."""
        if vgpu_uuids is None:
            vgpu_uuids = [['vgpu-11111111-1111-1111-1111-111111111111']]
        if mdev_uuids is None:
            mdev_uuids = [['a1b2c3d4-e5f6-7890-abcd-ef1234567890']]

        self.mock_pynvml.nvmlInit.return_value = None
        self.mock_pynvml.nvmlDeviceGetCount.return_value = gpu_count

        gpu_handles = []
        gpu_uuids_list = []
        for i in range(gpu_count):
            handle = mock.Mock(name=f'gpu_handle_{i}')
            gpu_handles.append(handle)
            gpu_uuids_list.append(
                f'GPU-{i:08d}-1234-1234-1234-123456789abc')

        self.mock_pynvml.nvmlDeviceGetHandleByIndex.side_effect = gpu_handles
        self.mock_pynvml.nvmlDeviceGetUUID.side_effect = gpu_uuids_list

        all_vgpu_instances = []
        vgpu_uuid_returns = []
        mdev_uuid_returns = []
        for gpu_idx in range(gpu_count):
            instances = [mock.Mock(name=f'vgpu_{gpu_idx}_{j}')
                         for j in range(len(vgpu_uuids[gpu_idx]))]
            all_vgpu_instances.append(instances)
            vgpu_uuid_returns.extend(vgpu_uuids[gpu_idx])
            mdev_uuid_returns.extend(mdev_uuids[gpu_idx])

        self.mock_pynvml.nvmlDeviceGetActiveVgpus.side_effect = \
            all_vgpu_instances
        self.mock_pynvml.nvmlVgpuInstanceGetUUID.side_effect = \
            vgpu_uuid_returns
        self.mock_pynvml.nvmlVgpuInstanceGetMdevUUID.side_effect = \
            mdev_uuid_returns

        # vGPU-specific utilization mock
        vgpu_util_sample = mock.Mock()
        vgpu_util_sample.vgpuInstance = all_vgpu_instances[0][0]
        vgpu_util_sample.smUtil = mock.Mock(uiVal=75)
        vgpu_util_sample.encUtil = mock.Mock(uiVal=30)
        vgpu_util_sample.decUtil = mock.Mock(uiVal=20)
        self.mock_pynvml.nvmlDeviceGetVgpuUtilization.return_value = \
            [vgpu_util_sample]

        # vGPU memory mocks
        self.mock_pynvml.nvmlVgpuInstanceGetFbUsage.return_value = \
            2048 * 1024 * 1024
        vgpu_type = mock.Mock()
        self.mock_pynvml.nvmlVgpuInstanceGetType.return_value = vgpu_type
        self.mock_pynvml.nvmlVgpuTypeGetFramebufferSize.return_value = \
            8192 * 1024 * 1024

    def test_inspect_gpus_one_vgpu(self):
        self._setup_nvml_mocks()

        domain = mock.Mock()
        domain.XMLDesc.return_value = DOMAIN_XML_ONE_VGPU
        domain.info.return_value = (1, 0, 0, 2, 999999)
        conn = mock.Mock()
        conn.lookupByUUIDString.return_value = domain

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            with mock.patch.object(self.inspector, '_init_nvml',
                                   return_value=True):
                with mock.patch.object(libvirt_inspector, 'pynvml',
                                       self.mock_pynvml):
                    stats = list(self.inspector.inspect_gpus(
                        self.instance, None))

        self.assertEqual(1, len(stats))
        self.assertEqual(75, stats[0].utilization)
        self.assertEqual(2048, stats[0].memory_used)
        self.assertEqual(8192, stats[0].memory_total)
        self.assertIsNone(stats[0].temperature)
        self.assertIsNone(stats[0].power_draw)
        self.assertEqual(30, stats[0].encoder_utilization)
        self.assertEqual(20, stats[0].decoder_utilization)

    def test_inspect_gpus_two_vgpus(self):
        self._setup_nvml_mocks(
            gpu_count=2,
            vgpu_uuids=[
                ['vgpu-11111111-1111-1111-1111-111111111111'],
                ['vgpu-22222222-2222-2222-2222-222222222222'],
            ],
            mdev_uuids=[
                ['a1b2c3d4-e5f6-7890-abcd-ef1234567890'],
                ['b2c3d4e5-f6a7-8901-bcde-f12345678901'],
            ])

        domain = mock.Mock()
        domain.XMLDesc.return_value = DOMAIN_XML_TWO_VGPUS
        domain.info.return_value = (1, 0, 0, 2, 999999)
        conn = mock.Mock()
        conn.lookupByUUIDString.return_value = domain

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            with mock.patch.object(self.inspector, '_init_nvml',
                                   return_value=True):
                with mock.patch.object(libvirt_inspector, 'pynvml',
                                       self.mock_pynvml):
                    stats = list(self.inspector.inspect_gpus(
                        self.instance, None))

        self.assertEqual(2, len(stats))
        devices = {s.device for s in stats}
        self.assertEqual({
            'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
            'b2c3d4e5-f6a7-8901-bcde-f12345678901',
        }, devices)

    def test_inspect_gpus_vm_no_gpu(self):
        domain = mock.Mock()
        domain.XMLDesc.return_value = DOMAIN_XML_NO_GPU
        domain.info.return_value = (1, 0, 0, 2, 999999)
        conn = mock.Mock()
        conn.lookupByUUIDString.return_value = domain

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            with mock.patch.object(self.inspector, '_init_nvml',
                                   return_value=True):
                stats = list(self.inspector.inspect_gpus(
                    self.instance, None))

        self.assertEqual(0, len(stats))

    def test_inspect_gpus_no_nvidia_hardware(self):
        """No GPU on node — should silently return empty."""
        with mock.patch.object(self.inspector, '_init_nvml',
                               return_value=None):
            stats = list(self.inspector.inspect_gpus(self.instance, None))

        self.assertEqual(0, len(stats))

    def test_inspect_gpus_nvml_unavailable(self):
        """GPU present but driver not accessible — should raise."""
        with mock.patch.object(self.inspector, '_init_nvml',
                               return_value=False):
            self.assertRaises(
                virt_inspector.NoDataException,
                list,
                self.inspector.inspect_gpus(self.instance, None))

    def test_init_nvml_success(self):
        self.inspector._nvml_available = libvirt_inspector._NVML_UNCHECKED
        with mock.patch.object(libvirt_inspector, 'pynvml',
                               self.mock_pynvml):
            self.mock_pynvml.nvmlInit.return_value = None
            result = self.inspector._init_nvml()

        self.assertTrue(result)
        self.assertTrue(self.inspector._nvml_available)

    def test_init_nvml_no_gpu_hardware(self):
        self.inspector._nvml_available = libvirt_inspector._NVML_UNCHECKED
        self.mock_pynvml.nvmlInit.side_effect = FakeNVMLError("no driver")
        with mock.patch.object(libvirt_inspector, 'pynvml',
                               self.mock_pynvml):
            with mock.patch.object(libvirt_inspector,
                                   '_has_nvidia_gpu_hardware',
                                   return_value=False):
                result = self.inspector._init_nvml()

        self.assertIsNone(result)

    def test_init_nvml_gpu_present_no_driver(self):
        self.inspector._nvml_available = libvirt_inspector._NVML_UNCHECKED
        self.mock_pynvml.nvmlInit.side_effect = FakeNVMLError("no driver")
        with mock.patch.object(libvirt_inspector, 'pynvml',
                               self.mock_pynvml):
            with mock.patch.object(libvirt_inspector,
                                   '_has_nvidia_gpu_hardware',
                                   return_value=True):
                result = self.inspector._init_nvml()

        self.assertFalse(result)
        self.assertFalse(self.inspector._nvml_available)

    def test_init_nvml_cached(self):
        self.inspector._nvml_available = True
        result = self.inspector._init_nvml()
        self.assertTrue(result)

    def test_init_nvml_no_gpu_cached(self):
        """Non-GPU nodes cache the None result and don't re-scan sysfs."""
        self.inspector._nvml_available = None
        with mock.patch.object(libvirt_inspector,
                               '_has_nvidia_gpu_hardware') as mock_hw:
            result = self.inspector._init_nvml()
        self.assertIsNone(result)
        mock_hw.assert_not_called()

    def test_get_mdev_uuids_from_domain(self):
        domain = mock.Mock()
        domain.XMLDesc.return_value = DOMAIN_XML_TWO_VGPUS
        uuids = libvirt_inspector.LibvirtInspector._get_mdev_uuids_from_domain(
            domain)
        self.assertEqual(2, len(uuids))
        self.assertIn('a1b2c3d4-e5f6-7890-abcd-ef1234567890', uuids)
        self.assertIn('b2c3d4e5-f6a7-8901-bcde-f12345678901', uuids)

    def test_get_mdev_uuids_no_gpu(self):
        domain = mock.Mock()
        domain.XMLDesc.return_value = DOMAIN_XML_NO_GPU
        uuids = libvirt_inspector.LibvirtInspector._get_mdev_uuids_from_domain(
            domain)
        self.assertEqual(0, len(uuids))

    def test_vgpu_map_caching(self):
        self._setup_nvml_mocks()

        with mock.patch.object(libvirt_inspector, 'pynvml',
                               self.mock_pynvml):
            map1 = self.inspector._build_vgpu_map()
            map2 = self.inspector._build_vgpu_map()

        self.assertIs(map1, map2)
        self.mock_pynvml.nvmlDeviceGetCount.assert_called_once()

    def test_vgpu_map_uses_mdev_uuid_as_key(self):
        self._setup_nvml_mocks()

        with mock.patch.object(libvirt_inspector, 'pynvml',
                               self.mock_pynvml):
            vgpu_map = self.inspector._build_vgpu_map()

        self.assertIn('a1b2c3d4-e5f6-7890-abcd-ef1234567890', vgpu_map)

    def test_partial_nvml_failure(self):
        """Individual metric failure should not prevent other metrics."""
        self._setup_nvml_mocks()
        self.mock_pynvml.nvmlVgpuInstanceGetFbUsage.side_effect = \
            FakeNVMLError("not supported")

        domain = mock.Mock()
        domain.XMLDesc.return_value = DOMAIN_XML_ONE_VGPU
        domain.info.return_value = (1, 0, 0, 2, 999999)
        conn = mock.Mock()
        conn.lookupByUUIDString.return_value = domain

        with mock.patch('ceilometer.compute.virt.libvirt.utils.'
                        'refresh_libvirt_connection', return_value=conn):
            with mock.patch.object(self.inspector, '_init_nvml',
                                   return_value=True):
                with mock.patch.object(libvirt_inspector, 'pynvml',
                                       self.mock_pynvml):
                    stats = list(self.inspector.inspect_gpus(
                        self.instance, None))

        self.assertEqual(1, len(stats))
        self.assertIsNone(stats[0].memory_used)
        self.assertEqual(75, stats[0].utilization)
