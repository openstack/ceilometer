# -*- encoding: utf-8 -*-
#
# Copyright © 2012 Red Hat, Inc
#
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
"""Implementation of Inspector abstraction for libvirt."""

from lxml import etree
from oslo.config import cfg

from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log as logging

libvirt = None

LOG = logging.getLogger(__name__)

libvirt_opts = [
    cfg.StrOpt('libvirt_type',
               default='kvm',
               help='Libvirt domain type (valid options are: '
                    'kvm, lxc, qemu, uml, xen).'),
    cfg.StrOpt('libvirt_uri',
               default='',
               help='Override the default libvirt URI '
                    '(which is dependent on libvirt_type).'),
]

CONF = cfg.CONF
CONF.register_opts(libvirt_opts)


class LibvirtInspector(virt_inspector.Inspector):

    per_type_uris = dict(uml='uml:///system', xen='xen:///', lxc='lxc:///')

    def __init__(self):
        self.uri = self._get_uri()
        self.connection = None

    def _get_uri(self):
        return CONF.libvirt_uri or self.per_type_uris.get(CONF.libvirt_type,
                                                          'qemu:///system')

    def _get_connection(self):
        if not self.connection or not self._test_connection():
            global libvirt
            if libvirt is None:
                libvirt = __import__('libvirt')

            LOG.debug(_('Connecting to libvirt: %s'), self.uri)
            self.connection = libvirt.openReadOnly(self.uri)

        return self.connection

    def _test_connection(self):
        try:
            self.connection.getCapabilities()
            return True
        except libvirt.libvirtError as e:
            if (e.get_error_code() == libvirt.VIR_ERR_SYSTEM_ERROR and
                e.get_error_domain() in (libvirt.VIR_FROM_REMOTE,
                                         libvirt.VIR_FROM_RPC)):
                LOG.debug(_('Connection to libvirt broke'))
                return False
            raise

    def _lookup_by_name(self, instance_name):
        try:
            return self._get_connection().lookupByName(instance_name)
        except Exception as ex:
            if not libvirt or not isinstance(ex, libvirt.libvirtError):
                raise virt_inspector.InspectorException(unicode(ex))
            error_code = ex.get_error_code()
            msg = ("Error from libvirt while looking up %(instance_name)s: "
                   "[Error Code %(error_code)s] "
                   "%(ex)s" % {'instance_name': instance_name,
                               'error_code': error_code,
                               'ex': ex})
            raise virt_inspector.InstanceNotFoundException(msg)

    def inspect_instances(self):
        if self._get_connection().numOfDomains() > 0:
            for domain_id in self._get_connection().listDomainsID():
                try:
                    # We skip domains with ID 0 (hypervisors).
                    if domain_id != 0:
                        domain = self._get_connection().lookupByID(domain_id)
                        yield virt_inspector.Instance(name=domain.name(),
                                                      UUID=domain.UUIDString())
                except libvirt.libvirtError:
                    # Instance was deleted while listing... ignore it
                    pass

    def inspect_cpus(self, instance_name):
        domain = self._lookup_by_name(instance_name)
        (__, __, __, num_cpu, cpu_time) = domain.info()
        return virt_inspector.CPUStats(number=num_cpu, time=cpu_time)

    def inspect_vnics(self, instance_name):
        domain = self._lookup_by_name(instance_name)
        (state, __, __, __, __) = domain.info()
        if state == libvirt.VIR_DOMAIN_SHUTOFF:
            LOG.warn(_('Failed to inspect vnics of %(instance_name)s, '
                       'domain is in state of SHUTOFF'),
                     {'instance_name': instance_name})
            return
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
            rx_bytes, rx_packets, __, __, \
                tx_bytes, tx_packets, __, __ = domain.interfaceStats(name)
            stats = virt_inspector.InterfaceStats(rx_bytes=rx_bytes,
                                                  rx_packets=rx_packets,
                                                  tx_bytes=tx_bytes,
                                                  tx_packets=tx_packets)
            yield (interface, stats)

    def inspect_disks(self, instance_name):
        domain = self._lookup_by_name(instance_name)
        (state, __, __, __, __) = domain.info()
        if state == libvirt.VIR_DOMAIN_SHUTOFF:
            LOG.warn(_('Failed to inspect disks of %(instance_name)s, '
                       'domain is in state of SHUTOFF'),
                     {'instance_name': instance_name})
            return
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
