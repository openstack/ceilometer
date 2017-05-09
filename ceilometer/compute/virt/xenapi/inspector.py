# Copyright 2014 Intel
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
"""Implementation of Inspector abstraction for XenAPI."""

from os_xenapi.client import session as xenapi_session
from os_xenapi.client import XenAPI
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import units

from ceilometer.compute.pollsters import util
from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.i18n import _

LOG = logging.getLogger(__name__)

opt_group = cfg.OptGroup(name='xenapi',
                         title='Options for XenAPI')

OPTS = [
    cfg.StrOpt('connection_url',
               help='URL for connection to XenServer/Xen Cloud Platform.'),
    cfg.StrOpt('connection_username',
               default='root',
               help='Username for connection to XenServer/Xen Cloud '
                    'Platform.'),
    cfg.StrOpt('connection_password',
               help='Password for connection to XenServer/Xen Cloud Platform.',
               secret=True),
]


class XenapiException(virt_inspector.InspectorException):
    pass


def get_api_session(conf):
    url = conf.xenapi.connection_url
    username = conf.xenapi.connection_username
    password = conf.xenapi.connection_password
    if not url or password is None:
        raise XenapiException(_('Must specify connection_url, and '
                                'connection_password to use'))

    try:
        session = xenapi_session.XenAPISession(url, username, password,
                                               originator="ceilometer")
        LOG.debug("XenAPI session is created successfully, %s", session)
    except XenAPI.Failure as e:
        msg = _("Could not connect to XenAPI: %s") % e.details[0]
        raise XenapiException(msg)
    return session


class XenapiInspector(virt_inspector.Inspector):

    def __init__(self, conf):
        super(XenapiInspector, self).__init__(conf)
        self.session = get_api_session(self.conf)

    def _lookup_by_name(self, instance_name):
        vm_refs = self.session.VM.get_by_name_label(instance_name)
        n = len(vm_refs)
        if n == 0:
            raise virt_inspector.InstanceNotFoundException(
                _('VM %s not found in XenServer') % instance_name)
        elif n > 1:
            raise XenapiException(
                _('Multiple VM %s found in XenServer') % instance_name)
        else:
            return vm_refs[0]

    def inspect_instance(self, instance, duration):
        instance_name = util.instance_name(instance)
        vm_ref = self._lookup_by_name(instance_name)
        cpu_util = self._get_cpu_usage(vm_ref, instance_name)
        memory_usage = self._get_memory_usage(vm_ref)
        LOG.debug("inspect_instance, cpu_util: %(cpu)s, memory_usage: %(mem)s",
                  {'cpu': cpu_util, 'mem': memory_usage}, instance=instance)
        return virt_inspector.InstanceStats(cpu_util=cpu_util,
                                            memory_usage=memory_usage)

    def _get_cpu_usage(self, vm_ref, instance_name):
        vcpus_number = int(self.session.VM.get_VCPUs_max(vm_ref))
        if vcpus_number <= 0:
            msg = _("Could not get VM %s CPU number") % instance_name
            raise XenapiException(msg)
        cpu_util = 0.0
        for index in range(vcpus_number):
            cpu_util += float(self.session.VM.query_data_source(
                vm_ref, "cpu%d" % index))
        return cpu_util / int(vcpus_number) * 100

    def _get_memory_usage(self, vm_ref):
        total_mem = float(self.session.VM.query_data_source(vm_ref, "memory"))
        try:
            free_mem = float(self.session.VM.query_data_source(
                vm_ref, "memory_internal_free"))
        except XenAPI.Failure:
            # If PV tools is not installed in the guest instance, it's
            # impossible to get free memory. So give it a default value
            # as 0.
            free_mem = 0
        # memory provided from XenServer is in Bytes;
        # memory_internal_free provided from XenServer is in KB,
        # converting it to MB.
        return (total_mem - free_mem * units.Ki) / units.Mi

    def inspect_vnics(self, instance, duration):
        instance_name = util.instance_name(instance)
        vm_ref = self._lookup_by_name(instance_name)
        dom_id = self.session.VM.get_domid(vm_ref)
        vif_refs = self.session.VM.get_VIFs(vm_ref)
        bw_all = self.session.call_plugin_serialized('bandwidth',
                                                     'fetch_all_bandwidth')
        LOG.debug("inspect_vnics, all bandwidth: %s", bw_all,
                  instance=instance)

        for vif_ref in vif_refs or []:
            vif_rec = self.session.VIF.get_record(vif_ref)

            bw_vif = bw_all[dom_id][vif_rec['device']]

            # TODO(jianghuaw): Currently the plugin can only support
            # rx_bytes and tx_bytes, so temporarily set others as -1.
            yield virt_inspector.InterfaceStats(
                name=vif_rec['uuid'],
                mac=vif_rec['MAC'],
                fref=None,
                parameters=None,
                rx_bytes=bw_vif['bw_in'], rx_packets=-1, rx_drop=-1,
                rx_errors=-1, tx_bytes=bw_vif['bw_out'], tx_packets=-1,
                tx_drop=-1, tx_errors=-1)

    def inspect_vnic_rates(self, instance, duration):
        instance_name = util.instance_name(instance)
        vm_ref = self._lookup_by_name(instance_name)
        vif_refs = self.session.VM.get_VIFs(vm_ref)
        if vif_refs:
            for vif_ref in vif_refs:
                vif_rec = self.session.VIF.get_record(vif_ref)

                rx_rate = float(self.session.VM.query_data_source(
                    vm_ref, "vif_%s_rx" % vif_rec['device']))
                tx_rate = float(self.session.VM.query_data_source(
                    vm_ref, "vif_%s_tx" % vif_rec['device']))

                yield virt_inspector.InterfaceRateStats(
                    name=vif_rec['uuid'],
                    mac=vif_rec['MAC'],
                    fref=None,
                    parameters=None,
                    rx_bytes_rate=rx_rate,
                    tx_bytes_rate=tx_rate)

    def inspect_disk_rates(self, instance, duration):
        instance_name = util.instance_name(instance)
        vm_ref = self._lookup_by_name(instance_name)
        vbd_refs = self.session.VM.get_VBDs(vm_ref)
        if vbd_refs:
            for vbd_ref in vbd_refs:
                vbd_rec = self.session.VBD.get_record(vbd_ref)

                read_rate = float(self.session.VM.query_data_source(
                    vm_ref, "vbd_%s_read" % vbd_rec['device']))
                write_rate = float(self.session.VM.query_data_source(
                    vm_ref, "vbd_%s_write" % vbd_rec['device']))
                yield virt_inspector.DiskRateStats(
                    device=vbd_rec['device'],
                    read_bytes_rate=read_rate,
                    read_requests_rate=0,
                    write_bytes_rate=write_rate,
                    write_requests_rate=0)
