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
