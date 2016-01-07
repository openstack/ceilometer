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

from oslo_config import cfg

from ceilometer.agent import plugin_base as plugin

cfg.CONF.import_group('service_credentials', 'ceilometer.keystone_client')


class TenantDiscovery(plugin.DiscoveryBase):
    """Discovery that supplies keystone tenants.

    This discovery should be used when the pollster's work can't be divided
    into smaller pieces than per-tenants. Example of this is the Swift
    pollster, which polls account details and does so per-project.
    """

    def discover(self, manager, param=None):
        tenants = manager.keystone.projects.list()
        return tenants or []
