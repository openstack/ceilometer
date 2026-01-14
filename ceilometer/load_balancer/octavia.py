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

from ceilometer.polling import plugin_base
from ceilometer import sample

LOG = log.getLogger(__name__)

# Octavia operating_status values mapped to numeric values
OPERATING_STATUS = {
    'online': 1,
    'draining': 2,
    'offline': 3,
    'degraded': 4,
    'error': 5,
    'no_monitor': 6,
}

# Octavia provisioning_status values mapped to numeric values
PROVISIONING_STATUS = {
    'active': 1,
    'deleted': 2,
    'error': 3,
    'pending_create': 4,
    'pending_update': 5,
    'pending_delete': 6,
}


class _BaseLoadBalancerPollster(plugin_base.PollsterBase):
    """Base pollster for Octavia load balancer metrics."""

    FIELDS = ['name',
              'availability_zone',
              'vip_address',
              'vip_port_id',
              'provisioning_status',
              'operating_status',
              'provider',
              'flavor_id',
              ]

    @property
    def default_discovery(self):
        return 'lb_services'

    @staticmethod
    def extract_metadata(lb):
        return {k: getattr(lb, k, None)
                for k in _BaseLoadBalancerPollster.FIELDS}


class LoadBalancerOperatingStatusPollster(_BaseLoadBalancerPollster):
    """Pollster for Octavia load balancer operating status."""

    @staticmethod
    def get_status_id(value):
        if not value:
            return -1
        status = value.lower()
        return OPERATING_STATUS.get(status, -1)

    def get_samples(self, manager, cache, resources):
        for lb in resources or []:
            LOG.debug("LOAD BALANCER: %s", lb)
            status = self.get_status_id(lb.operating_status)
            if status == -1:
                LOG.warning(
                    "Unknown operating status %(status)s for load balancer "
                    "%(name)s (%(id)s), setting volume to -1",
                    {"status": lb.operating_status,
                     "name": lb.name,
                     "id": lb.id})
            yield sample.Sample(
                name='loadbalancer.operating',
                type=sample.TYPE_GAUGE,
                unit='status',
                volume=status,
                user_id=None,
                project_id=lb.project_id,
                resource_id=lb.id,
                resource_metadata=self.extract_metadata(lb)
            )


class LoadBalancerProvisioningStatusPollster(_BaseLoadBalancerPollster):
    """Pollster for Octavia load balancer provisioning status."""

    @staticmethod
    def get_status_id(value):
        if not value:
            return -1
        status = value.lower()
        return PROVISIONING_STATUS.get(status, -1)

    def get_samples(self, manager, cache, resources):
        for lb in resources or []:
            LOG.debug("LOAD BALANCER: %s", lb)
            status = self.get_status_id(lb.provisioning_status)
            if status == -1:
                LOG.warning(
                    "Unknown provisioning status %(status)s for load "
                    "balancer %(name)s (%(id)s), setting volume to -1",
                    {"status": lb.provisioning_status,
                     "name": lb.name,
                     "id": lb.id})
            yield sample.Sample(
                name='loadbalancer.provisioning',
                type=sample.TYPE_GAUGE,
                unit='status',
                volume=status,
                user_id=None,
                project_id=lb.project_id,
                resource_id=lb.id,
                resource_metadata=self.extract_metadata(lb)
            )
