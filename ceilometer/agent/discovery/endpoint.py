# Copyright 2014-2015 Red Hat, Inc
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
from ceilometer import keystone_client

LOG = log.getLogger(__name__)


class EndpointDiscovery(plugin.DiscoveryBase):
    """Discovery that supplies service endpoints.

    This discovery should be used when the relevant APIs are not well suited
    to dividing the pollster's work into smaller pieces than a whole service
    at once.
    """

    def discover(self, manager, param=None):
        endpoints = keystone_client.get_service_catalog(
            manager.keystone).get_urls(
                service_type=param,
                interface=self.conf.service_credentials.interface,
                region_name=self.conf.service_credentials.region_name)
        if not endpoints:
            LOG.warning('No endpoints found for service %s',
                        "<all services>" if param is None else param)
            return []
        return endpoints
