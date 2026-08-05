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

from unittest import mock

from ceilometer.compute.pollsters import gpu
from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.polling import manager
from ceilometer.tests.unit.compute.pollsters import base


class TestVGPUPollster(base.TestPollsterBase):

    def setUp(self):
        super().setUp()
        self.gpu0 = virt_inspector.GPUStats(
            device='a1b2c3d4-e5f6-7890-abcd-ef1234567890',
            gpu_uuid='GPU-12345678-1234-1234-1234-123456789abc',
            vgpu_uuid='vgpu-11111111-1111-1111-1111-111111111111',
            utilization=75,
            memory_used=2048,
            memory_total=8192,
            temperature=None,
            power_draw=None,
            encoder_utilization=30,
            decoder_utilization=20)

        self.gpu1 = virt_inspector.GPUStats(
            device='b2c3d4e5-f6a7-8901-bcde-f12345678901',
            gpu_uuid='GPU-87654321-4321-4321-4321-cba987654321',
            vgpu_uuid='vgpu-22222222-2222-2222-2222-222222222222',
            utilization=50,
            memory_used=1024,
            memory_total=4096,
            temperature=None,
            power_draw=None,
            encoder_utilization=10,
            decoder_utilization=5)

        gpus = [self.gpu0, self.gpu1]
        self.inspector.inspect_gpus = mock.Mock(return_value=gpus)

    def _check_get_samples(self, factory, expected_name, expected_volumes):
        mgr = manager.AgentManager(0, self.CONF)
        pollster = factory(self.CONF)
        samples = list(pollster.get_samples(mgr, {}, [self.instance]))
        self.assertEqual(2, len(samples))
        self.assertEqual({expected_name}, {s.name for s in samples})

        actual_volumes = sorted([s.volume for s in samples])
        self.assertEqual(sorted(expected_volumes), actual_volumes)
        for sample in samples:
            self.assertEqual('gauge', sample.type)

        return samples

    def test_vgpu_utilization(self):
        self._check_get_samples(
            gpu.VGPUUtilizationPollster,
            'vgpu.utilization',
            sorted([75, 50]))

    def test_vgpu_memory_used(self):
        self._check_get_samples(
            gpu.VGPUMemoryUsedPollster,
            'vgpu.memory.used',
            sorted([2048, 1024]))

    def test_vgpu_memory_total(self):
        self._check_get_samples(
            gpu.VGPUMemoryTotalPollster,
            'vgpu.memory.total',
            sorted([8192, 4096]))

    def test_vgpu_encoder_utilization(self):
        self._check_get_samples(
            gpu.VGPUEncoderUtilizationPollster,
            'vgpu.encoder.utilization',
            sorted([30, 10]))

    def test_vgpu_decoder_utilization(self):
        self._check_get_samples(
            gpu.VGPUDecoderUtilizationPollster,
            'vgpu.decoder.utilization',
            sorted([20, 5]))

    def test_resource_id_format(self):
        mgr = manager.AgentManager(0, self.CONF)
        pollster = gpu.VGPUUtilizationPollster(self.CONF)
        samples = list(pollster.get_samples(mgr, {}, [self.instance]))
        resource_ids = {s.resource_id for s in samples}
        expected = {
            f"{self.instance.id}-{self.gpu0.device}",
            f"{self.instance.id}-{self.gpu1.device}",
        }
        self.assertEqual(expected, resource_ids)

    def test_additional_metadata(self):
        mgr = manager.AgentManager(0, self.CONF)
        pollster = gpu.VGPUUtilizationPollster(self.CONF)
        samples = list(pollster.get_samples(mgr, {}, [self.instance]))
        for sample in samples:
            self.assertIn('mdev_id', sample.resource_metadata)
            self.assertIn('gpu_id', sample.resource_metadata)
            self.assertIn('vgpu_id', sample.resource_metadata)

    def test_no_gpu_produces_no_samples(self):
        self.inspector.inspect_gpus = mock.Mock(return_value=[])
        mgr = manager.AgentManager(0, self.CONF)
        pollster = gpu.VGPUUtilizationPollster(self.CONF)
        samples = list(pollster.get_samples(mgr, {}, [self.instance]))
        self.assertEqual(0, len(samples))

    def test_none_stat_skipped(self):
        gpu_with_none = virt_inspector.GPUStats(
            device='c3d4e5f6-a7b8-9012-cdef-123456789012',
            gpu_uuid='GPU-11111111-1111-1111-1111-111111111111',
            vgpu_uuid='c3d4e5f6-a7b8-9012-cdef-123456789012',
            utilization=None,
            memory_used=1024,
            memory_total=4096,
            temperature=None,
            power_draw=None,
            encoder_utilization=0,
            decoder_utilization=0)
        self.inspector.inspect_gpus = mock.Mock(return_value=[gpu_with_none])
        mgr = manager.AgentManager(0, self.CONF)
        pollster = gpu.VGPUUtilizationPollster(self.CONF)
        samples = list(pollster.get_samples(mgr, {}, [self.instance]))
        self.assertEqual(0, len(samples))

    def test_metadata_without_vgpu_uuid(self):
        gpu_no_vgpu = virt_inspector.GPUStats(
            device='d4e5f6a7-b8c9-0123-defa-234567890123',
            gpu_uuid='GPU-22222222-2222-2222-2222-222222222222',
            vgpu_uuid=None,
            utilization=60,
            memory_used=512,
            memory_total=2048,
            temperature=None,
            power_draw=None,
            encoder_utilization=5,
            decoder_utilization=0)
        self.inspector.inspect_gpus = mock.Mock(return_value=[gpu_no_vgpu])
        mgr = manager.AgentManager(0, self.CONF)
        pollster = gpu.VGPUUtilizationPollster(self.CONF)
        samples = list(pollster.get_samples(mgr, {}, [self.instance]))
        self.assertEqual(1, len(samples))
        self.assertNotIn('vgpu_id', samples[0].resource_metadata)
        self.assertIn('mdev_id', samples[0].resource_metadata)
        self.assertIn('gpu_id', samples[0].resource_metadata)


class FakeGPUDevice:
    def __init__(self, index, gpu_uuid, name):
        self.index = index
        self.gpu_uuid = gpu_uuid
        self.name = name


class TestGPUPollster(base.TestPollsterBase):

    def setUp(self):
        super().setUp()
        self.gpu_devices = [
            FakeGPUDevice(0, 'GPU-aaaa-bbbb-cccc', 'NVIDIA A100'),
            FakeGPUDevice(1, 'GPU-dddd-eeee-ffff', 'NVIDIA A100'),
        ]

    def _mock_pynvml(self):
        mock_pynvml = mock.MagicMock()
        mock_pynvml.NVMLError = type('NVMLError', (Exception,), {})

        handles = [mock.Mock(), mock.Mock()]
        mock_pynvml.nvmlDeviceGetHandleByIndex.side_effect = handles

        rates0 = mock.Mock()
        rates0.gpu = 80
        rates1 = mock.Mock()
        rates1.gpu = 40
        mock_pynvml.nvmlDeviceGetUtilizationRates.side_effect = [
            rates0, rates1]

        mem0 = mock.Mock(used=4096 * 1024 * 1024, total=16384 * 1024 * 1024)
        mem1 = mock.Mock(used=2048 * 1024 * 1024, total=16384 * 1024 * 1024)
        mock_pynvml.nvmlDeviceGetMemoryInfo.side_effect = [mem0, mem1]

        mock_pynvml.nvmlDeviceGetTemperature.side_effect = [72, 58]
        mock_pynvml.nvmlDeviceGetPowerUsage.side_effect = [250000, 180000]
        mock_pynvml.nvmlDeviceGetEncoderUtilization.side_effect = [
            (15, 0), (5, 0)]
        mock_pynvml.nvmlDeviceGetDecoderUtilization.side_effect = [
            (10, 0), (3, 0)]

        return mock_pynvml

    @mock.patch.object(gpu.GPUPollster, '_init_nvml',
                       return_value=True)
    def test_physical_utilization(self, mock_init):
        mock_pynvml = self._mock_pynvml()
        with mock.patch.dict('sys.modules', {'pynvml': mock_pynvml}):
            pollster = gpu.GPUUtilizationPollster(self.CONF)
            samples = list(pollster.get_samples(None, {}, self.gpu_devices))

        self.assertEqual(2, len(samples))
        volumes = sorted([s.volume for s in samples])
        self.assertEqual([40, 80], volumes)
        for s in samples:
            self.assertEqual('gpu.utilization', s.name)
            self.assertEqual('%', s.unit)
            self.assertEqual('gauge', s.type)

    @mock.patch.object(gpu.GPUPollster, '_init_nvml',
                       return_value=True)
    def test_physical_temperature(self, mock_init):
        mock_pynvml = self._mock_pynvml()
        with mock.patch.dict('sys.modules', {'pynvml': mock_pynvml}):
            pollster = gpu.GPUTemperaturePollster(self.CONF)
            samples = list(pollster.get_samples(None, {}, self.gpu_devices))

        self.assertEqual(2, len(samples))
        volumes = sorted([s.volume for s in samples])
        self.assertEqual([58, 72], volumes)

    @mock.patch.object(gpu.GPUPollster, '_init_nvml',
                       return_value=True)
    def test_physical_power_draw(self, mock_init):
        mock_pynvml = self._mock_pynvml()
        with mock.patch.dict('sys.modules', {'pynvml': mock_pynvml}):
            pollster = gpu.GPUPowerDrawPollster(self.CONF)
            samples = list(pollster.get_samples(None, {}, self.gpu_devices))

        self.assertEqual(2, len(samples))
        volumes = sorted([s.volume for s in samples])
        self.assertEqual([180000, 250000], volumes)

    @mock.patch.object(gpu.GPUPollster, '_init_nvml',
                       return_value=True)
    def test_physical_resource_id(self, mock_init):
        mock_pynvml = self._mock_pynvml()
        with mock.patch.dict('sys.modules', {'pynvml': mock_pynvml}):
            pollster = gpu.GPUUtilizationPollster(self.CONF)
            samples = list(pollster.get_samples(None, {}, self.gpu_devices))

        resource_ids = {s.resource_id for s in samples}
        self.assertEqual({'GPU-aaaa-bbbb-cccc', 'GPU-dddd-eeee-ffff'},
                         resource_ids)

    @mock.patch.object(gpu.GPUPollster, '_init_nvml',
                       return_value=True)
    def test_physical_metadata(self, mock_init):
        mock_pynvml = self._mock_pynvml()
        with mock.patch.dict('sys.modules', {'pynvml': mock_pynvml}):
            pollster = gpu.GPUUtilizationPollster(self.CONF)
            samples = list(pollster.get_samples(None, {}, self.gpu_devices))

        for s in samples:
            self.assertIn('gpu_id', s.resource_metadata)
            self.assertIn('gpu_name', s.resource_metadata)
            self.assertEqual('NVIDIA A100', s.resource_metadata['gpu_name'])

    @mock.patch.object(gpu.GPUPollster, '_init_nvml',
                       return_value=False)
    def test_physical_no_nvml(self, mock_init):
        pollster = gpu.GPUUtilizationPollster(self.CONF)
        samples = list(pollster.get_samples(None, {}, self.gpu_devices))
        self.assertEqual(0, len(samples))

    @mock.patch.object(gpu.GPUPollster, '_init_nvml',
                       return_value=True)
    def test_physical_none_stat_skipped(self, mock_init):
        mock_pynvml = self._mock_pynvml()
        mock_pynvml.nvmlDeviceGetTemperature.side_effect = [
            mock_pynvml.NVMLError("not supported"),
            mock_pynvml.NVMLError("not supported")]
        with mock.patch.dict('sys.modules', {'pynvml': mock_pynvml}):
            pollster = gpu.GPUTemperaturePollster(self.CONF)
            samples = list(pollster.get_samples(None, {}, self.gpu_devices))

        self.assertEqual(0, len(samples))

    @mock.patch.object(gpu.GPUPollster, '_init_nvml',
                       return_value=True)
    def test_physical_caching(self, mock_init):
        mock_pynvml = self._mock_pynvml()
        with mock.patch.dict('sys.modules', {'pynvml': mock_pynvml}):
            cache = {}
            pollster = gpu.GPUUtilizationPollster(self.CONF)
            list(pollster.get_samples(None, cache, self.gpu_devices))
            # Reset side_effects so second call would fail if not cached
            mock_pynvml.nvmlDeviceGetHandleByIndex.side_effect = \
                Exception("should not be called")
            samples = list(pollster.get_samples(
                None, cache, self.gpu_devices))

        self.assertEqual(2, len(samples))
