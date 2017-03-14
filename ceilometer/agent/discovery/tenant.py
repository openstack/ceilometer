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

from ceilometer.agent import plugin_base as plugin

LOG = log.getLogger(__name__)


class TenantDiscovery(plugin.DiscoveryBase):
    """Discovery that supplies keystone tenants.

    This discovery should be used when the pollster's work can't be divided
    into smaller pieces than per-tenants. Example of this is the Swift
    pollster, which polls account details and does so per-project.
    """

    def discover(self, manager, param=None):
        domains = manager.keystone.domains.list()
        LOG.debug('Found %s keystone domains', len(domains))
        if domains:
            tenants = []
            for domain in domains:
                domain_tenants = manager.keystone.projects.list(domain)
                LOG.debug("Found %s tenants in domain %s", len(domain_tenants),
                          domain.name)
                tenants = tenants + domain_tenants
        else:
            tenants = manager.keystone.projects.list()
            LOG.debug("No domains - found %s tenants in default domain",
                      len(tenants))
        return tenants or []
