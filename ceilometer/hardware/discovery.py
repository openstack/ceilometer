# -*- encoding: utf-8 -*-
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

from oslo.config import cfg

from ceilometer import nova_client
from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log
from ceilometer import plugin


LOG = log.getLogger(__name__)

OPTS = [
    cfg.StrOpt('url_scheme',
               default='snmp://',
               help='URL scheme to use for hardware nodes'),
    cfg.StrOpt('readonly_user_name',
               default='ro_snmp_user',
               help='SNMPd user name of all nodes running in the cloud.'),
    cfg.StrOpt('readonly_user_password',
               default='password',
               help='SNMPd password of all the nodes running in the cloud'),
]
cfg.CONF.register_opts(OPTS, group='hardware')


class NodesDiscoveryTripleO(plugin.DiscoveryBase):
    def __init__(self):
        super(NodesDiscoveryTripleO, self).__init__()
        self.nova_cli = nova_client.Client()

    def discover(self, param=None):
        """Discover resources to monitor."""

        instances = self.nova_cli.instance_get_all()
        ip_addresses = []
        for instance in instances:
            try:
                ip_address = instance.addresses['ctlplane'][0]['addr']
                final_address = (
                    cfg.CONF.hardware.url_scheme +
                    cfg.CONF.hardware.readonly_user_name + ':' +
                    cfg.CONF.hardware.readonly_user_password + '@' +
                    ip_address)
                ip_addresses.append(final_address)
            except KeyError:
                LOG.error(_("Couldn't obtain IP address of"
                            "instance %s") % instance.id)

        return ip_addresses
