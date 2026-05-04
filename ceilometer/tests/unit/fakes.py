# Copyright (C) 2026 Red Hat
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

from keystoneauth1 import exceptions as ka_exceptions
from keystoneclient import exceptions as ks_exceptions
from keystoneclient.v3 import domains as ks_domains
from keystoneclient.v3 import projects as ks_projects
from openstack.network.v2 import firewall_group as sdk_firewall_group
from openstack.network.v2 import firewall_policy as sdk_firewall_policy
from openstack.network.v2 import floating_ip as sdk_floating_ip
from openstack.network.v2 import vpn_ipsec_site_connection as sdk_ipsec_conn
from openstack.network.v2 import vpn_service as sdk_vpn_service

from ceilometer import keystone_client


DOMAIN_DEFAULT = ks_domains.Domain(manager=None, info={
    'id': 'default', 'name': 'Default', 'enabled': True})
DOMAIN_DEFAULT_ceilo = keystone_client.Domain(
    id='default', name='Default', is_enabled=True)

DOMAIN_HEAT = ks_domains.Domain(manager=None, info={
    'id': '2f42ab40b7ad4140815ef830d816a16c', 'name': 'heat', 'enabled': True,
})
DOMAIN_HEAT_ceilo = keystone_client.Domain(
    id='2f42ab40b7ad4140815ef830d816a16c', name='heat', is_enabled=True)

DOMAIN_DISABLED = ks_domains.Domain(manager=None, info={
    'id': 'disabled-domain', 'name': 'Disabled', 'enabled': False})
DOMAIN_DISABLED_ceilo = keystone_client.Domain(
    id='disabled-domain', name='Disabled', is_enabled=False)

PROJECT_ADMIN = ks_projects.Project(manager=None, info={
    'id': '2ce92449a23145ef9c539f3327960ce3', 'name': 'admin',
    'parent_id': 'default', 'domain_id': 'default', 'is_domain': False,
    'enabled': True})
PROJECT_ADMIN_ceilo = keystone_client.Project(
    id='2ce92449a23145ef9c539f3327960ce3', name='admin', parent_id='default',
    domain_id='default', is_domain=False, is_enabled=True)

PROJECT_SERVICE = ks_projects.Project(manager=None, info={
    'id': 'a2d42c23-d518-46b6-96ab-3fba2e146859', 'name': 'service',
    'parent_id': 'default', 'domain_id': 'default', 'is_domain': False,
    'enabled': True})
PROJECT_SERVICE_ceilo = keystone_client.Project(
    id='a2d42c23-d518-46b6-96ab-3fba2e146859', name='service',
    parent_id='default', domain_id='default', is_domain=False, is_enabled=True)

PROJECT_DEMO = ks_projects.Project(manager=None, info={
    'id': '57d96b9af18d43bb9d047f436279b0be', 'name': 'demo',
    'parent_id': 'default',
    'domain_id': '2f42ab40b7ad4140815ef830d816a16c',
    'is_domain': False, 'enabled': True})
PROJECT_DEMO_ceilo = keystone_client.Project(
    id='57d96b9af18d43bb9d047f436279b0be', name='demo',
    parent_id='default', domain_id='2f42ab40b7ad4140815ef830d816a16c',
    is_domain=False, is_enabled=True)

PROJECT_DISABLED = ks_projects.Project(manager=None, info={
    'id': 'disabled-project', 'name': 'disabled',
    'parent_id': 'default', 'domain_id': 'default', 'is_domain': False,
    'enabled': False})
PROJECT_DISABLED_ceilo = keystone_client.Project(
    id='disabled-project', name='disabled', parent_id='default',
    domain_id='default', is_domain=False, is_enabled=False)


DEFAULT_PROJECTS = [
    PROJECT_ADMIN, PROJECT_SERVICE, PROJECT_DEMO, PROJECT_DISABLED]
DEFAULT_PROJECTS_ceilo = [
    PROJECT_ADMIN_ceilo, PROJECT_SERVICE_ceilo,
    PROJECT_DEMO_ceilo, PROJECT_DISABLED_ceilo]

DEFAULT_DOMAINS = [DOMAIN_HEAT, DOMAIN_DEFAULT]
DEFAULT_DOMAINS_ceilo = [DOMAIN_HEAT_ceilo, DOMAIN_DEFAULT_ceilo]


class FakeDomainManager:
    """Fake keystoneclient DomainManager."""

    def __init__(self, domains=None):
        self._domains = domains if domains is not None else []

    def list(self, **filters):
        if not filters:
            return self._domains
        return [d for d in self._domains
                if all(getattr(d, k, None) == v for k, v in filters.items())]

    def find(self, name=None, **kwargs):
        filters = dict(kwargs)
        if name is not None:
            filters['name'] = name
        found = self.list(**filters)
        if len(found) > 1:
            raise ks_exceptions.NoUniqueMatch
        if found:
            return found[0]
        raise ka_exceptions.NotFound(
            404, "No Domain matching %s." % filters)


class FakeProjectManager:
    """Fake keystoneclient ProjectManager."""

    def __init__(self, projects=None):
        self._projects = projects if projects is not None else []

    def list(self, domain=None, **filters):
        if domain is None and filters == {}:
            return self._projects

        projects = self._projects
        if domain:
            domain_id = getattr(domain, 'id', domain)
            projects = [p for p in projects if p.domain_id == domain_id]

        if filters:
            for k, v in filters.items():
                projects = [p for p in projects if getattr(p, k, None) == v]

        return projects

    def find(self, name=None, domain_id=None, **kwargs):
        filters = dict(kwargs)
        if name is not None:
            filters['name'] = name
        found = self.list(domain_id, **filters)
        if len(found) > 1:
            raise ks_exceptions.NoUniqueMatch
        if found:
            return found[0]
        raise ka_exceptions.NotFound(
            404, "No Project matching %s." % filters)


class FakeKeystoneClient:
    """Fake keystoneclient.v3.client.Client for testing."""

    def __init__(self, projects=None, domains=None):
        if projects is None:
            projects = DEFAULT_PROJECTS
        if domains is None:
            domains = DEFAULT_DOMAINS
        self.auth_token = 'fake_token'
        self.projects = FakeProjectManager(projects)
        self.domains = FakeDomainManager(domains)
        self.session = None


#####################
# SDK Fakes
#####################


class FakeSDKNetworkClient:

    def ips(self):
        FLOATING_IP_0 = sdk_floating_ip.FloatingIP(
            connection=None,
            id='fip-123',
            floating_ip_address='192.168.1.100',
            fixed_ip_address='10.0.0.5',
            status='ACTIVE',
            project_id='project-abc',
            router_id='router-456'
        )
        return iter([FLOATING_IP_0])

    def firewall_groups(self):
        FIREWALL_GROUP_0 = sdk_firewall_group.FirewallGroup(
            connection=None,
            id='fw-123',
            name='my-firewall',
            status='ACTIVE',
            project_id='project-abc',
            ingress_firewall_policy_id='policy-1',
            egress_firewall_policy_id='policy-2'
        )
        return iter([FIREWALL_GROUP_0])

    def firewall_policies(self):
        FIREWALL_POLICY_0 = sdk_firewall_policy.FirewallPolicy(
            connection=None,
            id='policy-123',
            name='my-policy',
            project_id='project-abc',
            firewall_rules=['rule-1', 'rule-2']
        )
        return iter([FIREWALL_POLICY_0])

    def vpn_ipsec_site_connections(self):
        VPN_IPSEC_CONN_0 = sdk_ipsec_conn.VpnIPSecSiteConnection(
            connection=None,
            id='ipsec-123',
            name='my-ipsec',
            status='ACTIVE',
            project_id='project-abc'
        )

        return iter([VPN_IPSEC_CONN_0])

    def vpn_services(self):

        VPN_SERVICE_0 = sdk_vpn_service.VpnService(
            connection=None,
            id='vpn-123',
            name='my-vpn',
            status='ACTIVE',
            project_id='project-abc'
        )

        return iter([VPN_SERVICE_0])


class FakeConnection:
    """Fake connection object for testing."""

    def __init__(self):
        """Initialize with a mock network attribute."""
        self.network = FakeSDKNetworkClient()
