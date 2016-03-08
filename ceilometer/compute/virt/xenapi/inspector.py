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

from oslo_config import cfg
from oslo_utils import units
import six.moves.urllib.parse as urlparse
try:
    import XenAPI as api
except ImportError:
    api = None

from ceilometer.compute.pollsters import util
from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.i18n import _

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

CONF = cfg.CONF
CONF.register_group(opt_group)
CONF.register_opts(OPTS, group=opt_group)


class XenapiException(virt_inspector.InspectorException):
    pass


def swap_xapi_host(url, host_addr):
    """Replace the XenServer address present in 'url' with 'host_addr'."""
    temp_url = urlparse.urlparse(url)
    # The connection URL is served by XAPI and doesn't support having a
    # path for the connection url after the port. And username/password
    # will be pass separately. So the URL like "http://abc:abc@abc:433/abc"
    # should not appear for XAPI case.
    temp_netloc = temp_url.netloc.replace(temp_url.hostname, '%s' % host_addr)
    replaced = temp_url._replace(netloc=temp_netloc)
    return urlparse.urlunparse(replaced)


def get_api_session():
    if not api:
        raise ImportError(_('XenAPI not installed'))

    url = CONF.xenapi.connection_url
    username = CONF.xenapi.connection_username
    password = CONF.xenapi.connection_password
    if not url or password is None:
        raise XenapiException(_('Must specify connection_url, and '
                                'connection_password to use'))

    try:
        session = (api.xapi_local() if url == 'unix://local'
                   else api.Session(url))
        session.login_with_password(username, password)
    except api.Failure as e:
        if e.details[0] == 'HOST_IS_SLAVE':
            master = e.details[1]
            url = swap_xapi_host(url, master)
            try:
                session = api.Session(url)
                session.login_with_password(username, password)
            except api.Failure as es:
                raise XenapiException(_('Could not connect slave host: %s ') %
                                      es.details[0])
        else:
            msg = _("Could not connect to XenAPI: %s") % e.details[0]
            raise XenapiException(msg)
    return session


class XenapiInspector(virt_inspector.Inspector):

    def __init__(self):
        super(XenapiInspector, self).__init__()
        self.session = get_api_session()

    def _get_host_ref(self):
        """Return the xenapi host on which nova-compute runs on."""
        return self.session.xenapi.session.get_this_host(self.session.handle)

    def _call_xenapi(self, method, *args):
        return self.session.xenapi_request(method, args)

    def _lookup_by_name(self, instance_name):
        vm_refs = self._call_xenapi("VM.get_by_name_label", instance_name)
        n = len(vm_refs)
        if n == 0:
            raise virt_inspector.InstanceNotFoundException(
                _('VM %s not found in XenServer') % instance_name)
        elif n > 1:
            raise XenapiException(
                _('Multiple VM %s found in XenServer') % instance_name)
        else:
            return vm_refs[0]

    def inspect_cpu_util(self, instance, duration=None):
        instance_name = util.instance_name(instance)
        vm_ref = self._lookup_by_name(instance_name)
        metrics_ref = self._call_xenapi("VM.get_metrics", vm_ref)
        metrics_rec = self._call_xenapi("VM_metrics.get_record",
                                        metrics_ref)
        vcpus_number = metrics_rec['VCPUs_number']
        vcpus_utils = metrics_rec['VCPUs_utilisation']
        if len(vcpus_utils) == 0:
            msg = _("Could not get VM %s CPU Utilization") % instance_name
            raise XenapiException(msg)

        utils = 0.0
        for num in range(int(vcpus_number)):
            utils += vcpus_utils.get(str(num))
        utils = utils / int(vcpus_number) * 100
        return virt_inspector.CPUUtilStats(util=utils)

    def inspect_memory_usage(self, instance, duration=None):
        instance_name = util.instance_name(instance)
        vm_ref = self._lookup_by_name(instance_name)
        metrics_ref = self._call_xenapi("VM.get_metrics", vm_ref)
        metrics_rec = self._call_xenapi("VM_metrics.get_record",
                                        metrics_ref)
        # Stat provided from XenServer is in B, converting it to MB.
        memory = int(metrics_rec['memory_actual']) / units.Mi
        return virt_inspector.MemoryUsageStats(usage=memory)

    def inspect_vnic_rates(self, instance, duration=None):
        instance_name = util.instance_name(instance)
        vm_ref = self._lookup_by_name(instance_name)
        vif_refs = self._call_xenapi("VM.get_VIFs", vm_ref)
        if vif_refs:
            for vif_ref in vif_refs:
                vif_rec = self._call_xenapi("VIF.get_record", vif_ref)
                vif_metrics_ref = self._call_xenapi(
                    "VIF.get_metrics", vif_ref)
                vif_metrics_rec = self._call_xenapi(
                    "VIF_metrics.get_record", vif_metrics_ref)

                interface = virt_inspector.Interface(
                    name=vif_rec['uuid'],
                    mac=vif_rec['MAC'],
                    fref=None,
                    parameters=None)
                rx_rate = float(vif_metrics_rec['io_read_kbs']) * units.Ki
                tx_rate = float(vif_metrics_rec['io_write_kbs']) * units.Ki
                stats = virt_inspector.InterfaceRateStats(rx_rate, tx_rate)
                yield (interface, stats)

    def inspect_disk_rates(self, instance, duration=None):
        instance_name = util.instance_name(instance)
        vm_ref = self._lookup_by_name(instance_name)
        vbd_refs = self._call_xenapi("VM.get_VBDs", vm_ref)
        if vbd_refs:
            for vbd_ref in vbd_refs:
                vbd_rec = self._call_xenapi("VBD.get_record", vbd_ref)
                vbd_metrics_ref = self._call_xenapi("VBD.get_metrics",
                                                    vbd_ref)
                vbd_metrics_rec = self._call_xenapi("VBD_metrics.get_record",
                                                    vbd_metrics_ref)

                disk = virt_inspector.Disk(device=vbd_rec['device'])
                # Stats provided from XenServer are in KB/s,
                # converting it to B/s.
                read_rate = float(vbd_metrics_rec['io_read_kbs']) * units.Ki
                write_rate = float(vbd_metrics_rec['io_write_kbs']) * units.Ki
                disk_rate_info = virt_inspector.DiskRateStats(
                    read_bytes_rate=read_rate,
                    read_requests_rate=0,
                    write_bytes_rate=write_rate,
                    write_requests_rate=0)
                yield(disk, disk_rate_info)
