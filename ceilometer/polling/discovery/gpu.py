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

from oslo_log import log

from ceilometer.polling import plugin_base

LOG = log.getLogger(__name__)

try:
    import pynvml
except ImportError:
    pynvml = None


class GPUDevice:
    """Represents a physical GPU for the discovery plugin."""

    def __init__(self, index, gpu_uuid, name):
        self.index = index
        self.id = gpu_uuid
        self.name = name
        self.gpu_uuid = gpu_uuid


class GPUDiscovery(plugin_base.DiscoveryBase):
    """Discover physical NVIDIA GPUs on the compute node via NVML."""

    def discover(self, manager, param=None):
        if pynvml is None:
            return []

        try:
            pynvml.nvmlInit()
        except pynvml.NVMLError:
            return []

        gpus = []
        try:
            count = pynvml.nvmlDeviceGetCount()
            for i in range(count):
                try:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    gpu_uuid = pynvml.nvmlDeviceGetUUID(handle)
                    name = pynvml.nvmlDeviceGetName(handle)
                    gpus.append(GPUDevice(i, gpu_uuid, name))
                except pynvml.NVMLError:
                    continue
        except pynvml.NVMLError:
            pass

        return gpus

    @property
    def group_id(self):
        return "local_gpus-%s" % self.conf.host
