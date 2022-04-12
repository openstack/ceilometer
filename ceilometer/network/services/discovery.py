#
# Copyright (c) 2014 Cisco Systems, Inc
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

from ceilometer import neutron_client
from ceilometer.polling import plugin_base


class _BaseServicesDiscovery(plugin_base.DiscoveryBase):
    KEYSTONE_REQUIRED_FOR_SERVICE = 'neutron'

    def __init__(self, conf):
        super(_BaseServicesDiscovery, self).__init__(conf)
        self.neutron_cli = neutron_client.Client(conf)


class VPNServicesDiscovery(_BaseServicesDiscovery):
    def discover(self, manager, param=None):
        """Discover resources to monitor."""

        vpnservices = self.neutron_cli.vpn_get_all()
        return [i for i in vpnservices
                if i.get('status', None) != 'error']


class IPSecConnectionsDiscovery(_BaseServicesDiscovery):
    def discover(self, manager, param=None):
        """Discover resources to monitor."""

        conns = self.neutron_cli.ipsec_site_connections_get_all()
        return conns


class FirewallDiscovery(_BaseServicesDiscovery):
    def discover(self, manager, param=None):
        """Discover resources to monitor."""

        fw = self.neutron_cli.firewall_get_all()
        return [i for i in fw
                if i.get('status', None) != 'error']


class FirewallPolicyDiscovery(_BaseServicesDiscovery):
    def discover(self, manager, param=None):
        """Discover resources to monitor."""

        return self.neutron_cli.fw_policy_get_all()


class FloatingIPDiscovery(_BaseServicesDiscovery):
    def discover(self, manager, param=None):
        """Discover floating IP resources to monitor."""

        return self.neutron_cli.fip_get_all()
