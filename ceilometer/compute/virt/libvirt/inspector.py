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
from ceilometer.i18n import _

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
    def inspect_vnics(self, instance, duration):
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
            dom_stats = domain.interfaceStats(name)
            yield virt_inspector.InterfaceStats(name=name,
                                                mac=mac_address,
                                                fref=fref,
                                                parameters=params,
                                                rx_bytes=dom_stats[0],
                                                rx_packets=dom_stats[1],
                                                rx_errors=dom_stats[2],
                                                rx_drop=dom_stats[3],
                                                tx_bytes=dom_stats[4],
                                                tx_packets=dom_stats[5],
                                                tx_errors=dom_stats[6],
                                                tx_drop=dom_stats[7])

    @libvirt_utils.retry_on_disconnect
    def inspect_disks(self, instance, duration):
        domain = self._get_domain_not_shut_off_or_raise(instance)

        tree = etree.fromstring(domain.XMLDesc(0))
        for device in filter(
                bool,
                [target.get("dev")
                 for target in tree.findall('devices/disk/target')
                 if target.getparent().find('source') is not None]):
            block_stats = domain.blockStats(device)
            yield virt_inspector.DiskStats(device=device,
                                           read_requests=block_stats[0],
                                           read_bytes=block_stats[1],
                                           write_requests=block_stats[2],
                                           write_bytes=block_stats[3],
                                           errors=block_stats[4])

    @libvirt_utils.retry_on_disconnect
    def inspect_disk_info(self, instance, duration):
        domain = self._get_domain_not_shut_off_or_raise(instance)
        tree = etree.fromstring(domain.XMLDesc(0))
        for disk in tree.findall('devices/disk'):
            # NOTE(lhx): "cdrom" device associated to the configdrive
            # no longer has a "source" element. Releated bug:
            # https://bugs.launchpad.net/ceilometer/+bug/1622718
            if disk.find('source') is None:
                continue
            target = disk.find('target')
            device = target.get('dev')
            if device:
                block_info = domain.blockInfo(device)
                yield virt_inspector.DiskInfo(device=device,
                                              capacity=block_info[0],
                                              allocation=block_info[1],
                                              physical=block_info[2])

    @libvirt_utils.raise_nodata_if_unsupported
    @libvirt_utils.retry_on_disconnect
    def inspect_instance(self, instance,  duration=None):
        domain = self._get_domain_not_shut_off_or_raise(instance)

        memory_used = memory_resident = None
        memory_swap_in = memory_swap_out = None
        memory_stats = domain.memoryStats()
        # Stat provided from libvirt is in KB, converting it to MB.
        if 'available' in memory_stats and 'unused' in memory_stats:
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
        cpu_time = 0
        current_cpus = stats.get('vcpu.current')
        # Iterate over the maximum number of CPUs here, and count the
        # actual number encountered, since the vcpu.x structure can
        # have holes according to
        # https://libvirt.org/git/?p=libvirt.git;a=blob;f=src/libvirt-domain.c
        # virConnectGetAllDomainStats()
        for vcpu in six.moves.range(stats.get('vcpu.maximum', 0)):
            try:
                cpu_time += (stats.get('vcpu.%s.time' % vcpu) +
                             stats.get('vcpu.%s.wait' % vcpu))
                current_cpus -= 1
            except TypeError:
                # pass here, if there are too many holes, the cpu count will
                # not match, so don't need special error handling.
                pass

        if current_cpus:
            # There wasn't enough data, so fall back
            cpu_time = stats.get('cpu.time')

        return virt_inspector.InstanceStats(
            cpu_number=stats.get('vcpu.current'),
            cpu_time=cpu_time,
            memory_usage=memory_used,
            memory_resident=memory_resident,
            memory_swap_in=memory_swap_in,
            memory_swap_out=memory_swap_out,
            cpu_cycles=stats.get("perf.cpu_cycles"),
            instructions=stats.get("perf.instructions"),
            cache_references=stats.get("perf.cache_references"),
            cache_misses=stats.get("perf.cache_misses"),
            memory_bandwidth_total=stats.get("perf.mbmt"),
            memory_bandwidth_local=stats.get("perf.mbml"),
            cpu_l3_cache_usage=stats.get("perf.cmt"),
        )
