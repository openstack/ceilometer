# Copyright 2014 Red Hat, Inc
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

from oslo_log import log

from ceilometer.polling import plugin_base as plugin

LOG = log.getLogger(__name__)


class TenantDiscovery(plugin.DiscoveryBase):
    """Discovery that supplies keystone tenants.

    This discovery should be used when the pollster's work can't be divided
    into smaller pieces than per-tenants. Example of this is the Swift
    pollster, which polls account details and does so per-project.
    """

    def discover(self, manager, param=None):
        domains = manager.keystone.domains.list()
        LOG.debug(f"Found {len(domains)} keystone domains")

        tenants = []
        for domain in domains:
            domain_tenants = manager.keystone.projects.list(domain)
            if self.conf.polling.ignore_disabled_projects:
                enabled_tenants = [tenant for tenant in
                                   domain_tenants if tenant.enabled]
                LOG.debug(f"Found {len(enabled_tenants)} enabled "
                          f"tenants in domain {domain.name}")
                tenants = enabled_tenants + domain_tenants
            else:
                LOG.debug(f"Found {len(domain_tenants)} "
                          f"tenants in domain {domain.name}")
                tenants = tenants + domain_tenants

        return tenants or []
