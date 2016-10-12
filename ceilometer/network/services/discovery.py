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

from ceilometer.agent import plugin_base
from ceilometer import neutron_client


class _BaseServicesDiscovery(plugin_base.DiscoveryBase):
    KEYSTONE_REQUIRED_FOR_SERVICE = 'neutron'

    def __init__(self, conf):
        super(_BaseServicesDiscovery, self).__init__(conf)
        self.neutron_cli = neutron_client.Client(conf)


class LBPoolsDiscovery(_BaseServicesDiscovery):
    def discover(self, manager, param=None):
        """Discover resources to monitor."""

        pools = self.neutron_cli.pool_get_all()
        return [i for i in pools
                if i.get('status') != 'error']


class LBVipsDiscovery(_BaseServicesDiscovery):
    def discover(self, manager, param=None):
        """Discover resources to monitor."""

        vips = self.neutron_cli.vip_get_all()
        return [i for i in vips
                if i.get('status', None) != 'error']


class LBMembersDiscovery(_BaseServicesDiscovery):
    def discover(self, manager, param=None):
        """Discover resources to monitor."""

        members = self.neutron_cli.member_get_all()
        return [i for i in members
                if i.get('status', None) != 'error']


class LBListenersDiscovery(_BaseServicesDiscovery):
    def discover(self, manager, param=None):
        """Discover load balancer listener resources to monitor."""

        listeners = self.neutron_cli.list_listener()
        return [i for i in listeners
                if i.get('operating_status', None) != 'error']


class LBLoadBalancersDiscovery(_BaseServicesDiscovery):
    def discover(self, manager, param=None):
        """Discover load balancer resources to monitor."""

        loadbalancers = self.neutron_cli.list_loadbalancer()
        return [i for i in loadbalancers
                if i.get('operating_status', None) != 'error']


class LBHealthMonitorsDiscovery(_BaseServicesDiscovery):
    def discover(self, manager, param=None):
        """Discover resources to monitor."""

        probes = self.neutron_cli.health_monitor_get_all()
        return probes


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
