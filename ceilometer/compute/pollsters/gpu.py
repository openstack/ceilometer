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
from ceilometer.compute import pollsters
from ceilometer.polling import plugin_base
from ceilometer import sample


class VGPUPollster(pollsters.GenericComputePollster):
    inspector_method = 'inspect_gpus'

    @staticmethod
    def get_resource_id(instance, stats):
        return f"{instance.id}-{stats.device}"

    @staticmethod
    def get_additional_metadata(instance, stats):
        metadata = {'mdev_id': stats.device}
        if stats.gpu_uuid:
            metadata['gpu_id'] = stats.gpu_uuid
        if stats.vgpu_uuid:
            metadata['vgpu_id'] = stats.vgpu_uuid
        return metadata


class VGPUUtilizationPollster(VGPUPollster):
    sample_name = 'vgpu.utilization'
    sample_unit = '%'
    sample_stats_key = 'utilization'


class VGPUMemoryUsedPollster(VGPUPollster):
    sample_name = 'vgpu.memory.used'
    sample_unit = 'MiB'
    sample_stats_key = 'memory_used'


class VGPUMemoryTotalPollster(VGPUPollster):
    sample_name = 'vgpu.memory.total'
    sample_unit = 'MiB'
    sample_stats_key = 'memory_total'


class VGPUEncoderUtilizationPollster(VGPUPollster):
    sample_name = 'vgpu.encoder.utilization'
    sample_unit = '%'
    sample_stats_key = 'encoder_utilization'


class VGPUDecoderUtilizationPollster(VGPUPollster):
    sample_name = 'vgpu.decoder.utilization'
    sample_unit = '%'
    sample_stats_key = 'decoder_utilization'


class GPUPollster(plugin_base.PollsterBase):
    """Pollster for physical GPU metrics, discovered per-GPU not per-VM."""

    sample_name = None
    sample_unit = ''
    sample_type = sample.TYPE_GAUGE
    sample_stats_key = None

    _nvml_initialized = False

    @property
    def default_discovery(self):
        return 'local_gpus'

    @staticmethod
    def _init_nvml():
        if not GPUPollster._nvml_initialized:
            try:
                import pynvml
                pynvml.nvmlInit()
                GPUPollster._nvml_initialized = True
            except Exception:
                return False
        return True

    def get_samples(self, manager, cache, resources):
        if not self._init_nvml():
            return

        import pynvml

        cache.setdefault('gpu_physical', {})

        for gpu_dev in resources:
            if gpu_dev.index not in cache['gpu_physical']:
                try:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_dev.index)
                    stats = {}

                    try:
                        rates = pynvml.nvmlDeviceGetUtilizationRates(handle)
                        stats['utilization'] = rates.gpu
                    except pynvml.NVMLError:
                        stats['utilization'] = None

                    try:
                        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                        stats['memory_used'] = mem.used // (1024 * 1024)
                        stats['memory_total'] = mem.total // (1024 * 1024)
                    except pynvml.NVMLError:
                        stats['memory_used'] = None
                        stats['memory_total'] = None

                    try:
                        stats['temperature'] = pynvml.nvmlDeviceGetTemperature(
                            handle, pynvml.NVML_TEMPERATURE_GPU)
                    except pynvml.NVMLError:
                        stats['temperature'] = None

                    try:
                        stats['power_draw'] = \
                            pynvml.nvmlDeviceGetPowerUsage(handle)
                    except pynvml.NVMLError:
                        stats['power_draw'] = None

                    try:
                        enc, _ = pynvml.nvmlDeviceGetEncoderUtilization(
                            handle)
                        stats['encoder_utilization'] = enc
                    except pynvml.NVMLError:
                        stats['encoder_utilization'] = None

                    try:
                        dec, _ = pynvml.nvmlDeviceGetDecoderUtilization(
                            handle)
                        stats['decoder_utilization'] = dec
                    except pynvml.NVMLError:
                        stats['decoder_utilization'] = None

                    cache['gpu_physical'][gpu_dev.index] = stats
                except pynvml.NVMLError:
                    continue

            stats = cache['gpu_physical'].get(gpu_dev.index)
            if not stats:
                continue

            volume = stats.get(self.sample_stats_key)
            if volume is None:
                continue

            yield sample.Sample(
                name=self.sample_name,
                type=self.sample_type,
                unit=self.sample_unit,
                volume=volume,
                user_id=None,
                project_id=None,
                resource_id=gpu_dev.gpu_uuid,
                resource_metadata={
                    'gpu_id': gpu_dev.gpu_uuid,
                    'gpu_name': gpu_dev.name,
                    'host': self.conf.host,
                },
            )


class GPUUtilizationPollster(GPUPollster):
    sample_name = 'gpu.utilization'
    sample_unit = '%'
    sample_stats_key = 'utilization'


class GPUMemoryUsedPollster(GPUPollster):
    sample_name = 'gpu.memory.used'
    sample_unit = 'MiB'
    sample_stats_key = 'memory_used'


class GPUMemoryTotalPollster(GPUPollster):
    sample_name = 'gpu.memory.total'
    sample_unit = 'MiB'
    sample_stats_key = 'memory_total'


class GPUTemperaturePollster(GPUPollster):
    sample_name = 'gpu.temperature'
    sample_unit = 'C'
    sample_stats_key = 'temperature'


class GPUPowerDrawPollster(GPUPollster):
    sample_name = 'gpu.power.draw'
    sample_unit = 'mW'
    sample_stats_key = 'power_draw'


class GPUEncoderUtilizationPollster(GPUPollster):
    sample_name = 'gpu.encoder.utilization'
    sample_unit = '%'
    sample_stats_key = 'encoder_utilization'


class GPUDecoderUtilizationPollster(GPUPollster):
    sample_name = 'gpu.decoder.utilization'
    sample_unit = '%'
    sample_stats_key = 'decoder_utilization'
