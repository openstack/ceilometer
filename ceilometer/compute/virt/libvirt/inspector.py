#
# Copyright 2012 Red Hat, Inc
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
"""Implementation of Inspector abstraction for libvirt."""

import glob

import cachetools
from lxml import etree
from oslo_log import log as logging
from oslo_utils import units

try:
    import libvirt
except ImportError:
    libvirt = None

try:
    import pynvml
except ImportError:
    pynvml = None

from ceilometer.compute.pollsters import util
from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.compute.virt.libvirt import utils as libvirt_utils
from ceilometer.i18n import _

LOG = logging.getLogger(__name__)


_NVML_UNCHECKED = object()

NVIDIA_PCI_VENDOR_ID = '0x10de'
NVIDIA_GPU_PCI_CLASS_PREFIX = '0x03'


def _has_nvidia_gpu_hardware():
    """Check if any NVIDIA GPU is present via sysfs PCI devices."""
    for vendor_path in glob.glob('/sys/bus/pci/devices/*/vendor'):
        try:
            with open(vendor_path) as f:
                if f.read().strip() == NVIDIA_PCI_VENDOR_ID:
                    class_path = vendor_path.replace('vendor', 'class')
                    with open(class_path) as cf:
                        if cf.read().strip().startswith(
                                NVIDIA_GPU_PCI_CLASS_PREFIX):
                            return True
        except OSError:
            continue
    return False


class LibvirtInspector(virt_inspector.Inspector):

    def __init__(self, conf):
        super().__init__(conf)
        # NOTE(sileht): create a connection on startup
        self.connection
        self.cache = {}
        self._nvml_available = _NVML_UNCHECKED

    @property
    def connection(self):
        return libvirt_utils.refresh_libvirt_connection(self.conf, self)

    def _lookup_by_uuid(self, instance):
        instance_name = util.instance_name(instance)
        try:
            return self.connection.lookupByUUIDString(instance.id)
        except libvirt.libvirtError as ex:
            if libvirt_utils.is_disconnection_exception(ex):
                raise
            msg = _("Error from libvirt while looking up instance "
                    "<name=%(name)s, id=%(id)s>: "
                    "[Error Code %(error_code)s] "
                    "%(ex)s") % {'name': instance_name,
                                 'id': instance.id,
                                 'error_code': ex.get_error_code(),
                                 'ex': ex}
            raise virt_inspector.InstanceNotFoundException(msg)
        except Exception as ex:
            raise virt_inspector.InspectorException(str(ex))

    def _get_domain(self, instance, raise_if_shutoff):
        instance_name = util.instance_name(instance)
        domain = self._lookup_by_uuid(instance)

        if raise_if_shutoff:
            state = domain.info()[0]
            if state == libvirt.VIR_DOMAIN_SHUTOFF:
                msg = _('Failed to inspect data of instance '
                        '<name=%(name)s, id=%(id)s>, '
                        'domain state is SHUTOFF.') % {
                    'name': instance_name, 'id': instance.id}
                raise virt_inspector.InstanceShutOffException(msg)

        return domain

    @libvirt_utils.retry_on_disconnect
    def inspect_vnics(self, instance, duration):
        domain = self._get_domain(instance, True)

        tree = etree.fromstring(domain.XMLDesc(0))
        for iface in tree.findall('devices/interface'):
            target = iface.find('target')
            if target is not None:
                name = target.get('dev')
            else:
                continue
            mac = iface.find('mac')
            if mac is not None:
                mac_address = mac.get('address')
            else:
                continue
            fref = iface.find('filterref')
            if fref is not None:
                fref = fref.get('filter')

            params = {p.get('name').lower(): p.get('value')
                      for p in iface.findall('filterref/parameter')}

            # Extract interface ID
            try:
                interfaceid = iface.find('virtualport').find(
                    'parameters').get('interfaceid')
            except AttributeError:
                interfaceid = None

            # Extract source bridge
            try:
                bridge = iface.find('source').get('bridge')
            except AttributeError:
                bridge = None

            params['interfaceid'] = interfaceid
            params['bridge'] = bridge

            try:
                dom_stats = domain.interfaceStats(name)
            except libvirt.libvirtError as ex:
                LOG.warning("Error from libvirt when running interfaceStats, "
                            "This may not be harmful, but please check : "
                            "%(ex)s",
                            {'ex': ex})
                continue

            # Retrieve previous values
            prev = self.cache.get(name)

            # Store values for next call
            self.cache[name] = dom_stats

            if prev:
                # Compute stats
                rx_delta = dom_stats[0] - prev[0]
                tx_delta = dom_stats[4] - prev[4]

                # Avoid negative values
                if rx_delta < 0:
                    rx_delta = dom_stats[0]
                if tx_delta < 0:
                    tx_delta = dom_stats[4]
            else:
                LOG.debug('No delta meter predecessor for %s / %s',
                          instance.id, name)
                rx_delta = 0
                tx_delta = 0

            yield virt_inspector.InterfaceStats(name=name,
                                                mac=mac_address,
                                                fref=fref,
                                                parameters=params,
                                                rx_bytes=dom_stats[0],
                                                rx_packets=dom_stats[1],
                                                rx_errors=dom_stats[2],
                                                rx_drop=dom_stats[3],
                                                rx_bytes_delta=rx_delta,
                                                tx_bytes=dom_stats[4],
                                                tx_packets=dom_stats[5],
                                                tx_errors=dom_stats[6],
                                                tx_drop=dom_stats[7],
                                                tx_bytes_delta=tx_delta)

    @staticmethod
    def _get_disk_devices(domain):
        tree = etree.fromstring(domain.XMLDesc(0))
        return filter(bool, [target.get("dev") for target in
                             tree.findall('devices/disk/target')
                             if target.getparent().find('source') is not None])

    @libvirt_utils.retry_on_disconnect
    def inspect_disks(self, instance, duration):
        domain = self._get_domain(instance, True)
        for device in self._get_disk_devices(domain):
            try:
                block_stats = domain.blockStats(device)
                block_stats_flags = domain.blockStatsFlags(device, 0)
                yield virt_inspector.DiskStats(
                    device=device,
                    read_requests=block_stats[0], read_bytes=block_stats[1],
                    write_requests=block_stats[2], write_bytes=block_stats[3],
                    errors=block_stats[4],
                    wr_total_times=block_stats_flags['wr_total_times'],
                    rd_total_times=block_stats_flags['rd_total_times'])
            except libvirt.libvirtError as ex:
                # raised error even if lock is acquired while live migration,
                # even it looks normal.
                LOG.warning("Error from libvirt while checking blockStats, "
                            "This may not be harmful, but please check : "
                            "%(ex)s", {'ex': ex})
                pass

    @libvirt_utils.retry_on_disconnect
    def inspect_disk_info(self, instance, duration):
        domain = self._get_domain(
            instance, not self.conf.compute.report_stopped_instance_metrics)
        for device in self._get_disk_devices(domain):
            block_info = domain.blockInfo(device)
            # if vm mount cdrom, libvirt will align by 4K bytes, capacity may
            # be smaller than physical, avoid with this.
            # https://libvirt.org/html/libvirt-libvirt-domain.html
            disk_capacity = max(block_info[0], block_info[2])
            yield virt_inspector.DiskInfo(device=device,
                                          capacity=disk_capacity,
                                          allocation=block_info[1],
                                          physical=block_info[2])

    @libvirt_utils.raise_nodata_if_unsupported
    @libvirt_utils.retry_on_disconnect
    def inspect_instance(self, instance, duration=None):
        domain = self._get_domain(
            instance, not self.conf.compute.report_stopped_instance_metrics)

        if self.conf.compute.report_stopped_instance_metrics:
            dom_info = domain.info()
            state = dom_info[0]
            if state == libvirt.VIR_DOMAIN_SHUTOFF:
                return virt_inspector.InstanceStats(
                    power_state=state,
                    cpu_number=dom_info[3],
                    memory_actual=dom_info[1] / units.Ki,
                )

        memory_actual = None
        memory_available = None
        memory_used = memory_resident = None
        memory_swap_in = memory_swap_out = None
        memory_stats = domain.memoryStats()
        # Stat provided from libvirt is in KiB, converting it to MiB.
        if 'actual' in memory_stats:
            memory_actual = memory_stats['actual'] / units.Ki
        if 'available' in memory_stats:
            memory_available = memory_stats['available'] / units.Ki
        if 'usable' in memory_stats and 'available' in memory_stats:
            memory_used = (memory_stats['available'] -
                           memory_stats['usable']) / units.Ki
        elif 'available' in memory_stats and 'unused' in memory_stats:
            memory_used = (memory_stats['available'] -
                           memory_stats['unused']) / units.Ki
        if 'rss' in memory_stats:
            memory_resident = memory_stats['rss'] / units.Ki
        if 'swap_in' in memory_stats and 'swap_out' in memory_stats:
            memory_swap_in = memory_stats['swap_in'] / units.Ki
            memory_swap_out = memory_stats['swap_out'] / units.Ki

        # TODO(sileht): stats also have the disk/vnic info
        # we could use that instead of the old method for Queen
        stats = self.connection.domainListGetStats([domain], 0)[0][1]
        cpu_time = cpu_delay = 0
        current_cpus = stats.get('vcpu.current')
        # Iterate over the maximum number of CPUs here, and count the
        # actual number encountered, since the vcpu.x structure can
        # have holes according to
        # https://libvirt.org/git/?p=libvirt.git;a=blob;f=src/libvirt-domain.c
        # virConnectGetAllDomainStats()
        for vcpu in range(stats.get('vcpu.maximum', 0)):
            try:
                cpu_time += (stats.get('vcpu.%s.time' % vcpu) +
                             stats.get('vcpu.%s.wait' % vcpu))
                cpu_delay += stats.get('vcpu.%s.delay' % vcpu)
                current_cpus -= 1
            except TypeError:
                # pass here, if there are too many holes, the cpu count will
                # not match, so don't need special error handling.
                pass

        if current_cpus:
            # There wasn't enough data, so fall back
            cpu_time = stats.get('cpu.time')
            cpu_delay = 0

        return virt_inspector.InstanceStats(
            power_state=domain.info()[0],
            cpu_number=stats.get('vcpu.current'),
            cpu_time=cpu_time,
            cpu_delay=cpu_delay,
            memory_actual=memory_actual,
            memory_available=memory_available,
            memory_usage=memory_used,
            memory_resident=memory_resident,
            memory_swap_in=memory_swap_in,
            memory_swap_out=memory_swap_out,
            cpu_cycles=stats.get("perf.cpu_cycles"),
            instructions=stats.get("perf.instructions"),
            cache_references=stats.get("perf.cache_references"),
            cache_misses=stats.get("perf.cache_misses")
        )

    def _init_nvml(self):
        """Initialize NVML lazily.

        Returns True (available), False (GPU present, driver missing),
        or None (no GPU hardware -- silent).
        """
        if self._nvml_available is not _NVML_UNCHECKED:
            return self._nvml_available

        if pynvml is None:
            if _has_nvidia_gpu_hardware():
                self._nvml_available = False
                return False
            self._nvml_available = None
            return None

        try:
            pynvml.nvmlInit()
            self._nvml_available = True
            return True
        except pynvml.NVMLError:
            if _has_nvidia_gpu_hardware():
                self._nvml_available = False
                return False
            self._nvml_available = None
            return None

    @cachetools.cached(cache=cachetools.TTLCache(maxsize=1, ttl=120))
    def _build_vgpu_map(self):
        """Build a map of mdev UUID to (gpu_handle, vgpu_instance).

        Cached per poll cycle via monotonic timestamp.
        """
        vgpu_map = {}
        try:
            gpu_count = pynvml.nvmlDeviceGetCount()
        except pynvml.NVMLError:
            return vgpu_map

        for i in range(gpu_count):
            try:
                gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                gpu_uuid = pynvml.nvmlDeviceGetUUID(gpu_handle)
                active_vgpus = pynvml.nvmlDeviceGetActiveVgpus(gpu_handle)
                for vgpu_instance in active_vgpus:
                    try:
                        vgpu_uuid = pynvml.nvmlVgpuInstanceGetUUID(
                            vgpu_instance)
                        vgpu_uuid = vgpu_uuid.lower().strip()
                        mdev_uuid = pynvml.nvmlVgpuInstanceGetMdevUUID(
                            vgpu_instance)
                        mdev_uuid = mdev_uuid.lower().strip()
                        vgpu_map[mdev_uuid] = (gpu_handle, gpu_uuid,
                                               vgpu_instance,
                                               vgpu_uuid)
                    except pynvml.NVMLError:
                        continue
            except pynvml.NVMLError:
                continue

        return vgpu_map

    @staticmethod
    def _get_mdev_uuids_from_domain(domain):
        """Extract mdev UUIDs from a libvirt domain's XML."""
        tree = etree.fromstring(domain.XMLDesc(0))
        mdev_uuids = []
        for hostdev in tree.findall('devices/hostdev'):
            if (hostdev.get('type') == 'mdev'
                    and hostdev.get('mode') == 'subsystem'):
                source = hostdev.find('source')
                if source is not None:
                    address = source.find('address')
                    if address is not None:
                        uuid = address.get('uuid')
                        if uuid:
                            mdev_uuids.append(uuid.lower().strip())
        return mdev_uuids

    @staticmethod
    def _get_vgpu_stats(gpu_handle, gpu_uuid, vgpu_instance, vgpu_uuid,
                        device_id):
        """Collect per-vGPU metrics using NVML vGPU-specific APIs."""
        utilization = None
        memory_used = None
        memory_total = None
        encoder_utilization = None
        decoder_utilization = None

        try:
            samples = pynvml.nvmlDeviceGetVgpuUtilization(gpu_handle, 0)
            for s in samples:
                if s.vgpuInstance == vgpu_instance:
                    utilization = s.smUtil.uiVal
                    encoder_utilization = s.encUtil.uiVal
                    decoder_utilization = s.decUtil.uiVal
                    break
        except (pynvml.NVMLError, AttributeError):
            pass

        try:
            fb_bytes = pynvml.nvmlVgpuInstanceGetFbUsage(vgpu_instance)
            memory_used = fb_bytes // (1024 * 1024)
        except pynvml.NVMLError:
            pass

        try:
            vgpu_type = pynvml.nvmlVgpuInstanceGetType(vgpu_instance)
            fb_size = pynvml.nvmlVgpuTypeGetFramebufferSize(vgpu_type)
            memory_total = fb_size // (1024 * 1024)
        except pynvml.NVMLError:
            pass

        return virt_inspector.GPUStats(
            device=device_id,
            gpu_uuid=gpu_uuid,
            vgpu_uuid=vgpu_uuid,
            utilization=utilization,
            memory_used=memory_used,
            memory_total=memory_total,
            temperature=None,
            power_draw=None,
            encoder_utilization=encoder_utilization,
            decoder_utilization=decoder_utilization,
        )


    @libvirt_utils.retry_on_disconnect
    def inspect_gpus(self, instance, duration):
        nvml_state = self._init_nvml()

        if nvml_state is None:
            return

        if nvml_state is False:
            raise virt_inspector.NoDataException(
                'NVIDIA GPU hardware detected but NVML is not available. '
                'Ensure the NVIDIA driver is installed and libnvidia-ml.so '
                'is accessible in the container.')

        domain = self._get_domain(instance, True)
        mdev_uuids = self._get_mdev_uuids_from_domain(domain)
        if not mdev_uuids:
            return

        vgpu_map = self._build_vgpu_map()

        for idx, mdev_uuid in enumerate(mdev_uuids):
            if mdev_uuid in vgpu_map:
                gpu_handle, gpu_uuid, vgpu_instance, vgpu_uuid = \
                    vgpu_map[mdev_uuid]
                device_id = mdev_uuid
                yield self._get_vgpu_stats(
                    gpu_handle, gpu_uuid, vgpu_instance,
                    vgpu_uuid, device_id)
