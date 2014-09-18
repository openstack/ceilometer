#
# Copyright 2014 Red Hat, Inc
#
# Author: Nejc Saje <nsaje@redhat.com>
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

from ceilometer.openstack.common.gettextutils import _LW
from ceilometer.openstack.common import log
from ceilometer import plugin

LOG = log.getLogger(__name__)

cfg.CONF.import_group('service_credentials', 'ceilometer.service')


class EndpointDiscovery(plugin.DiscoveryBase):
    """Discovery that supplies service endpoints.

    This discovery should be used when the relevant APIs are not well suited
    to dividing the pollster's work into smaller pieces than a whole service
    at once. Example of this is the floating_ip pollster which calls
    nova.floating_ips.list() and therefore gets all floating IPs at once.
    """

    def discover(self, manager, param=None):
        if not param:
            return []
        endpoints = manager.keystone.service_catalog.get_urls(
            service_type=param,
            endpoint_type=cfg.CONF.service_credentials.os_endpoint_type,
            region_name=cfg.CONF.service_credentials.os_region_name)
        if not endpoints:
            LOG.warning(_LW('No endpoints found for service %s'), param)
            return []
        else:
            return endpoints


class TenantDiscovery(plugin.DiscoveryBase):
    """Discovery that supplies keystone tenants.

    This discovery should be used when the pollster's work can't be divided
    into smaller pieces than per-tenant. Example of this is the Swift
    pollster, which polls account details and does so per-tenant.
    """

    def discover(self, manager, param=None):
        tenants = manager.keystone.tenants.list()
        return tenants or []
