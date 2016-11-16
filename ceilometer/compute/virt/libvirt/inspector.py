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

from lxml import etree
from oslo_log import log as logging
from oslo_utils import units
import six

try:
    import libvirt
except ImportError:
    libvirt = None

from ceilometer.compute.pollsters import util
from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.compute.virt.libvirt import utils as libvirt_utils
from ceilometer.i18n import _LW, _

LOG = logging.getLogger(__name__)


class LibvirtInspector(virt_inspector.Inspector):

    def __init__(self, conf):
        super(LibvirtInspector, self).__init__(conf)
        # NOTE(sileht): create a connection on startup
        self.connection

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
            raise virt_inspector.InspectorException(six.text_type(ex))

    @libvirt_utils.retry_on_disconnect
    def inspect_cpus(self, instance):
        domain = self._get_domain_not_shut_off_or_raise(instance)
        # TODO(gordc): this can probably be cached since it can be used to get
        # all data related
        stats = self.connection.domainListGetStats([domain])
        dom_stat = stats[0][1]
        return virt_inspector.CPUStats(number=dom_stat['vcpu.current'],
                                       time=dom_stat['cpu.time'])

    @libvirt_utils.raise_nodata_if_unsupported("l3 cache usage")
    @libvirt_utils.retry_on_disconnect
    def inspect_cpu_l3_cache(self, instance):
        domain = self._lookup_by_uuid(instance)
        stats = self.connection.domainListGetStats(
            [domain], libvirt.VIR_DOMAIN_STATS_PERF)
        perf = stats[0][1]
        usage = perf["perf.cmt"]
        return virt_inspector.CPUL3CacheUsageStats(l3_cache_usage=usage)

    def _get_domain_not_shut_off_or_raise(self, instance):
        instance_name = util.instance_name(instance)
        domain = self._lookup_by_uuid(instance)

        state = domain.info()[0]
        if state == libvirt.VIR_DOMAIN_SHUTOFF:
            msg = _('Failed to inspect data of instance '
                    '<name=%(name)s, id=%(id)s>, '
                    'domain state is SHUTOFF.') % {
                'name': instance_name, 'id': instance.id}
            raise virt_inspector.InstanceShutOffException(msg)

        return domain

    @libvirt_utils.retry_on_disconnect
    def inspect_vnics(self, instance):
        domain = self._get_domain_not_shut_off_or_raise(instance)

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

            params = dict((p.get('name').lower(), p.get('value'))
                          for p in iface.findall('filterref/parameter'))
            interface = virt_inspector.Interface(name=name, mac=mac_address,
                                                 fref=fref, parameters=params)
            dom_stats = domain.interfaceStats(name)
            stats = virt_inspector.InterfaceStats(rx_bytes=dom_stats[0],
                                                  rx_packets=dom_stats[1],
                                                  rx_drop=dom_stats[2],
                                                  rx_errors=dom_stats[3],
                                                  tx_bytes=dom_stats[4],
                                                  tx_packets=dom_stats[5],
                                                  tx_drop=dom_stats[6],
                                                  tx_errors=dom_stats[7])
            yield (interface, stats)

    @libvirt_utils.retry_on_disconnect
    def inspect_disks(self, instance):
        domain = self._get_domain_not_shut_off_or_raise(instance)

        tree = etree.fromstring(domain.XMLDesc(0))
        for device in filter(
                bool,
                [target.get("dev")
                 for target in tree.findall('devices/disk/target')]):
            disk = virt_inspector.Disk(device=device)
            block_stats = domain.blockStats(device)
            stats = virt_inspector.DiskStats(read_requests=block_stats[0],
                                             read_bytes=block_stats[1],
                                             write_requests=block_stats[2],
                                             write_bytes=block_stats[3],
                                             errors=block_stats[4])
            yield (disk, stats)

    @libvirt_utils.raise_nodata_if_unsupported("memory usge", False)
    @libvirt_utils.retry_on_disconnect
    def inspect_memory_usage(self, instance, duration=None):
        domain = self._get_domain_not_shut_off_or_raise(instance)

        memory_stats = domain.memoryStats()
        memory_used = (memory_stats['available'] -
                       memory_stats['unused'])
        # Stat provided from libvirt is in KB, converting it to MB.
        memory_used = memory_used / units.Ki
        return virt_inspector.MemoryUsageStats(usage=memory_used)

    @libvirt_utils.retry_on_disconnect
    def inspect_disk_info(self, instance):
        domain = self._get_domain_not_shut_off_or_raise(instance)
        tree = etree.fromstring(domain.XMLDesc(0))
        for disk in tree.findall('devices/disk'):
            disk_type = disk.get('type')
            if disk_type:
                if disk_type == 'network':
                    LOG.warning(
                        _LW('Inspection disk usage of network disk '
                            '%(instance_uuid)s unsupported by libvirt') % {
                            'instance_uuid': instance.id})
                    continue
                # NOTE(lhx): "cdrom" device associated to the configdrive
                # no longer has a "source" element. Releated bug:
                # https://bugs.launchpad.net/ceilometer/+bug/1622718
                if disk.find('source') is None:
                    continue
                target = disk.find('target')
                device = target.get('dev')
                if device:
                    dsk = virt_inspector.Disk(device=device)
                    block_info = domain.blockInfo(device)
                    info = virt_inspector.DiskInfo(capacity=block_info[0],
                                                   allocation=block_info[1],
                                                   physical=block_info[2])
                    yield (dsk, info)

    @libvirt_utils.retry_on_disconnect
    def inspect_memory_resident(self, instance, duration=None):
        domain = self._get_domain_not_shut_off_or_raise(instance)
        memory = domain.memoryStats()['rss'] / units.Ki
        return virt_inspector.MemoryResidentStats(resident=memory)

    @libvirt_utils.raise_nodata_if_unsupported("memory bandwidth")
    @libvirt_utils.retry_on_disconnect
    def inspect_memory_bandwidth(self, instance, duration=None):
        domain = self._get_domain_not_shut_off_or_raise(instance)
        stats = self.connection.domainListGetStats(
            [domain], libvirt.VIR_DOMAIN_STATS_PERF)
        perf = stats[0][1]
        return virt_inspector.MemoryBandwidthStats(total=perf["perf.mbmt"],
                                                   local=perf["perf.mbml"])

    @libvirt_utils.raise_nodata_if_unsupported("perf events")
    @libvirt_utils.retry_on_disconnect
    def inspect_perf_events(self, instance, duration=None):
        domain = self._get_domain_not_shut_off_or_raise(instance)

        stats = self.connection.domainListGetStats(
            [domain], libvirt.VIR_DOMAIN_STATS_PERF)
        perf = stats[0][1]
        return virt_inspector.PerfEventsStats(
            cpu_cycles=perf["perf.cpu_cycles"],
            instructions=perf["perf.instructions"],
            cache_references=perf["perf.cache_references"],
            cache_misses=perf["perf.cache_misses"])
