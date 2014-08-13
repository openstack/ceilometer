#
# Copyright 2012 Red Hat, Inc
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
import six

from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.openstack.common.gettextutils import _
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


def retry_on_disconnect(function):
    def decorator(self, *args, **kwargs):
        try:
            return function(self, *args, **kwargs)
        except libvirt.libvirtError as e:
            if (e.get_error_code() == libvirt.VIR_ERR_SYSTEM_ERROR and
                e.get_error_domain() in (libvirt.VIR_FROM_REMOTE,
                                         libvirt.VIR_FROM_RPC)):
                LOG.debug('Connection to libvirt broken')
                self.connection = None
                return function(self, *args, **kwargs)
            else:
                raise
    return decorator


class LibvirtInspector(virt_inspector.Inspector):

    per_type_uris = dict(uml='uml:///system', xen='xen:///', lxc='lxc:///')

    def __init__(self):
        self.uri = self._get_uri()
        self.connection = None

    def _get_uri(self):
        return CONF.libvirt_uri or self.per_type_uris.get(CONF.libvirt_type,
                                                          'qemu:///system')

    def _get_connection(self):
        if not self.connection:
            global libvirt
            if libvirt is None:
                libvirt = __import__('libvirt')
            LOG.debug('Connecting to libvirt: %s', self.uri)
            self.connection = libvirt.openReadOnly(self.uri)

        return self.connection

    @retry_on_disconnect
    def _lookup_by_name(self, instance_name):
        try:
            return self._get_connection().lookupByName(instance_name)
        except Exception as ex:
            if not libvirt or not isinstance(ex, libvirt.libvirtError):
                raise virt_inspector.InspectorException(six.text_type(ex))
            error_code = ex.get_error_code()
            if (error_code == libvirt.VIR_ERR_SYSTEM_ERROR and
                ex.get_error_domain() in (libvirt.VIR_FROM_REMOTE,
                                          libvirt.VIR_FROM_RPC)):
                raise
            msg = ("Error from libvirt while looking up %(instance_name)s: "
                   "[Error Code %(error_code)s] "
                   "%(ex)s" % {'instance_name': instance_name,
                               'error_code': error_code,
                               'ex': ex})
            raise virt_inspector.InstanceNotFoundException(msg)

    @retry_on_disconnect
    def inspect_instance(self, domain_id):
        domain = self._get_connection().lookupByID(domain_id)
        return virt_inspector.Instance(name=domain.name(),
                                       UUID=domain.UUIDString())

    @retry_on_disconnect
    def inspect_instances(self):
        if self._get_connection().numOfDomains() > 0:
            for domain_id in self._get_connection().listDomainsID():
                if domain_id != 0:
                    try:
                        yield self.inspect_instance(domain_id)
                    except libvirt.libvirtError:
                        # Instance was deleted while listing... ignore it
                        pass

    def inspect_cpus(self, instance_name):
        domain = self._lookup_by_name(instance_name)
        dom_info = domain.info()
        return virt_inspector.CPUStats(number=dom_info[3], time=dom_info[4])

    def inspect_vnics(self, instance_name):
        domain = self._lookup_by_name(instance_name)
        state = domain.info()[0]
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
            dom_stats = domain.interfaceStats(name)
            stats = virt_inspector.InterfaceStats(rx_bytes=dom_stats[0],
                                                  rx_packets=dom_stats[1],
                                                  tx_bytes=dom_stats[4],
                                                  tx_packets=dom_stats[5])
            yield (interface, stats)

    def inspect_disks(self, instance_name):
        domain = self._lookup_by_name(instance_name)
        state = domain.info()[0]
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
