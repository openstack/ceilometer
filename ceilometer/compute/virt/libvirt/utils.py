#
# Copyright 2016 Red Hat, Inc
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

from oslo_config import cfg
from oslo_log import log as logging
import tenacity

try:
    import libvirt
except ImportError:
    libvirt = None

from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.i18n import _

LOG = logging.getLogger(__name__)

OPTS = [
    cfg.StrOpt('libvirt_type',
               default='kvm',
               choices=['kvm', 'lxc', 'qemu', 'uml', 'xen'],
               help='Libvirt domain type.'),
    cfg.StrOpt('libvirt_uri',
               default='',
               help='Override the default libvirt URI '
                    '(which is dependent on libvirt_type).'),
]

LIBVIRT_PER_TYPE_URIS = dict(uml='uml:///system', xen='xen:///', lxc='lxc:///')


# We don't use the libvirt constants in case of libvirt is not available
VIR_DOMAIN_NOSTATE = 0
VIR_DOMAIN_RUNNING = 1
VIR_DOMAIN_BLOCKED = 2
VIR_DOMAIN_PAUSED = 3
VIR_DOMAIN_SHUTDOWN = 4
VIR_DOMAIN_SHUTOFF = 5
VIR_DOMAIN_CRASHED = 6
VIR_DOMAIN_PMSUSPENDED = 7

# Stolen from nova
LIBVIRT_POWER_STATE = {
    VIR_DOMAIN_NOSTATE: 'pending',
    VIR_DOMAIN_RUNNING: 'running',
    VIR_DOMAIN_BLOCKED: 'running',
    VIR_DOMAIN_PAUSED: 'paused',
    VIR_DOMAIN_SHUTDOWN: 'shutdown',
    VIR_DOMAIN_SHUTOFF: 'shutdown',
    VIR_DOMAIN_CRASHED: 'crashed',
    VIR_DOMAIN_PMSUSPENDED: 'suspended',
}

# NOTE(sileht): This is a guessing of the nova
# status, should be true 99.9% on the time,
# but can be wrong during some transition state
# like shelving/rescuing
LIBVIRT_STATUS = {
    VIR_DOMAIN_NOSTATE: 'building',
    VIR_DOMAIN_RUNNING: 'active',
    VIR_DOMAIN_BLOCKED: 'active',
    VIR_DOMAIN_PAUSED: 'paused',
    VIR_DOMAIN_SHUTDOWN: 'stopped',
    VIR_DOMAIN_SHUTOFF: 'stopped',
    VIR_DOMAIN_CRASHED: 'error',
    VIR_DOMAIN_PMSUSPENDED: 'suspended',
}


def new_libvirt_connection(conf):
    if not libvirt:
        raise ImportError("python-libvirt module is missing")
    uri = (conf.libvirt_uri or LIBVIRT_PER_TYPE_URIS.get(conf.libvirt_type,
                                                         'qemu:///system'))
    LOG.debug('Connecting to libvirt: %s', uri)
    return libvirt.openReadOnly(uri)


def refresh_libvirt_connection(conf, klass):
    connection = getattr(klass, '_libvirt_connection', None)
    if not connection or not connection.isAlive():
        connection = new_libvirt_connection(conf)
        setattr(klass, '_libvirt_connection', connection)
    return connection


def is_disconnection_exception(e):
    if not libvirt:
        return False
    return (isinstance(e, libvirt.libvirtError)
            and e.get_error_code() in (libvirt.VIR_ERR_SYSTEM_ERROR,
                                       libvirt.VIR_ERR_INTERNAL_ERROR)
            and e.get_error_domain() in (libvirt.VIR_FROM_REMOTE,
                                         libvirt.VIR_FROM_RPC))


retry_on_disconnect = tenacity.retry(
    retry=tenacity.retry_if_exception(is_disconnection_exception),
    stop=tenacity.stop_after_attempt(2))


def raise_nodata_if_unsupported(method):
    def inner(in_self, instance, *args, **kwargs):
        try:
            return method(in_self, instance, *args, **kwargs)
        except libvirt.libvirtError as e:
            # NOTE(sileht): At this point libvirt connection error
            # have been reraise as tenacity.RetryError()
            msg = _('Failed to inspect instance %(instance_uuid)s stats, '
                    'can not get info from libvirt: %(error)s') % {
                        "instance_uuid": instance.id,
                        "error": e}
            raise virt_inspector.NoDataException(msg)
    return inner
