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
        filters = {}
        # When ignore_disabled_projects is enabled, add a filter
        # to the Keystone API queries so that only enabled projects,
        # and projects in enabled domains, are returned.
        if self.conf.polling.ignore_disabled_projects:
            filters["enabled"] = True

        domains = manager.keystone.domains.list(**filters)
        LOG.debug(
            "Found %i %sKeystone domains",
            len(domains),
            "enabled " if self.conf.polling.ignore_disabled_projects else "")

        tenants = []
        projects_log_message = (
            "Found %i enabled projects in domain %s"
            if self.conf.polling.ignore_disabled_projects
            else "Found %i projects in domain %s")
        for domain in domains:
            domain_projects = manager.keystone.projects.list(
                domain,
                **filters)
            LOG.debug(projects_log_message, len(domain_projects), domain.name)
            tenants.extend(domain_projects)

        return tenants
