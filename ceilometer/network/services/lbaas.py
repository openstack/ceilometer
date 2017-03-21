#
# Copyright 2014 Cisco Systems,Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import abc
import collections

from oslo_log import log
import six

from ceilometer.i18n import _
from ceilometer.network.services import base
from ceilometer import neutron_client
from ceilometer import sample

LOG = log.getLogger(__name__)

LBStatsData = collections.namedtuple(
    'LBStats',
    ['active_connections', 'total_connections', 'bytes_in', 'bytes_out']
)

LOAD_BALANCER_STATUS_V2 = {
    'offline': 0,
    'online': 1,
    'no_monitor': 3,
    'error': 4,
    'degraded': 5,
    'disabled': 6
}


class BaseLBPollster(base.BaseServicesPollster):
    """Base Class for Load Balancer pollster"""

    def __init__(self, conf):
        super(BaseLBPollster, self).__init__(conf)
        self.lb_version = self.conf.service_types.neutron_lbaas_version

    def get_load_balancer_status_id(self, value):
        if self.lb_version == 'v1':
            resource_status = self.get_status_id(value)
        elif self.lb_version == 'v2':
            status = value.lower()
            resource_status = LOAD_BALANCER_STATUS_V2.get(status, -1)
        return resource_status


class LBPoolPollster(BaseLBPollster):
    """Pollster to capture Load Balancer pool status samples."""

    FIELDS = ['admin_state_up',
              'description',
              'lb_method',
              'name',
              'protocol',
              'provider',
              'status',
              'status_description',
              'subnet_id',
              'vip_id'
              ]

    @property
    def default_discovery(self):
        return 'lb_pools'

    def get_samples(self, manager, cache, resources):
        resources = resources or []

        for pool in resources:
            LOG.debug("Load Balancer Pool : %s" % pool)
            status = self.get_load_balancer_status_id(pool['status'])
            if status == -1:
                # unknown status, skip this sample
                LOG.warning(_("Unknown status %(stat)s received on pool "
                              "%(id)s, skipping sample")
                            % {'stat': pool['status'], 'id': pool['id']})
                continue

            yield sample.Sample(
                name='network.services.lb.pool',
                type=sample.TYPE_GAUGE,
                unit='pool',
                volume=status,
                user_id=None,
                project_id=pool['tenant_id'],
                resource_id=pool['id'],
                resource_metadata=self.extract_metadata(pool)
            )


class LBVipPollster(base.BaseServicesPollster):
    """Pollster to capture Load Balancer Vip status samples."""

    FIELDS = ['admin_state_up',
              'address',
              'connection_limit',
              'description',
              'name',
              'pool_id',
              'port_id',
              'protocol',
              'protocol_port',
              'status',
              'status_description',
              'subnet_id',
              'session_persistence',
              ]

    @property
    def default_discovery(self):
        return 'lb_vips'

    def get_samples(self, manager, cache, resources):
        resources = resources or []

        for vip in resources:
            LOG.debug("Load Balancer Vip : %s" % vip)
            status = self.get_status_id(vip['status'])
            if status == -1:
                # unknown status, skip this sample
                LOG.warning(_("Unknown status %(stat)s received on vip "
                              "%(id)s, skipping sample")
                            % {'stat': vip['status'], 'id': vip['id']})
                continue

            yield sample.Sample(
                name='network.services.lb.vip',
                type=sample.TYPE_GAUGE,
                unit='vip',
                volume=status,
                user_id=None,
                project_id=vip['tenant_id'],
                resource_id=vip['id'],
                resource_metadata=self.extract_metadata(vip)
            )


class LBMemberPollster(BaseLBPollster):
    """Pollster to capture Load Balancer Member status samples."""

    FIELDS = ['admin_state_up',
              'address',
              'pool_id',
              'protocol_port',
              'status',
              'status_description',
              'weight',
              ]

    @property
    def default_discovery(self):
        return 'lb_members'

    def get_samples(self, manager, cache, resources):
        resources = resources or []

        for member in resources:
            LOG.debug("Load Balancer Member : %s" % member)
            status = self.get_load_balancer_status_id(member['status'])
            if status == -1:
                LOG.warning(_("Unknown status %(stat)s received on member "
                              "%(id)s, skipping sample")
                            % {'stat': member['status'], 'id': member['id']})
                continue
            yield sample.Sample(
                name='network.services.lb.member',
                type=sample.TYPE_GAUGE,
                unit='member',
                volume=status,
                user_id=None,
                project_id=member['tenant_id'],
                resource_id=member['id'],
                resource_metadata=self.extract_metadata(member)
            )


class LBHealthMonitorPollster(base.BaseServicesPollster):
    """Pollster to capture Load Balancer Health probes status samples."""

    FIELDS = ['admin_state_up',
              'delay',
              'max_retries',
              'pools',
              'timeout',
              'type'
              ]

    @property
    def default_discovery(self):
        return 'lb_health_probes'

    def get_samples(self, manager, cache, resources):
        for probe in resources:
            LOG.debug("Load Balancer Health probe : %s" % probe)
            yield sample.Sample(
                name='network.services.lb.health_monitor',
                type=sample.TYPE_GAUGE,
                unit='health_monitor',
                volume=1,
                user_id=None,
                project_id=probe['tenant_id'],
                resource_id=probe['id'],
                resource_metadata=self.extract_metadata(probe)
            )


@six.add_metaclass(abc.ABCMeta)
class _LBStatsPollster(base.BaseServicesPollster):
    """Base Statistics pollster.

     It is capturing the statistics info and yielding samples for connections
     and bandwidth.
    """

    def __init__(self, conf):
        super(_LBStatsPollster, self).__init__(conf)
        self.client = neutron_client.Client(self.conf)
        self.lb_version = self.conf.service_types.neutron_lbaas_version

    @staticmethod
    def make_sample_from_pool(pool, name, type, unit, volume,
                              resource_metadata=None):
        if not resource_metadata:
            resource_metadata = {}
        return sample.Sample(
            name=name,
            type=type,
            unit=unit,
            volume=volume,
            user_id=None,
            project_id=pool['tenant_id'],
            resource_id=pool['id'],
            resource_metadata=resource_metadata,
        )

    def _populate_stats_cache(self, pool_id, cache):
        i_cache = cache.setdefault("lbstats", {})
        if pool_id not in i_cache:
            stats = self.client.pool_stats(pool_id)['stats']
            i_cache[pool_id] = LBStatsData(
                active_connections=stats['active_connections'],
                total_connections=stats['total_connections'],
                bytes_in=stats['bytes_in'],
                bytes_out=stats['bytes_out'],
            )
        return i_cache[pool_id]

    def _populate_stats_cache_v2(self, loadbalancer_id, cache):
        i_cache = cache.setdefault("lbstats", {})
        if loadbalancer_id not in i_cache:
            stats = self.client.get_loadbalancer_stats(loadbalancer_id)
            i_cache[loadbalancer_id] = LBStatsData(
                active_connections=stats['active_connections'],
                total_connections=stats['total_connections'],
                bytes_in=stats['bytes_in'],
                bytes_out=stats['bytes_out'],
            )
        return i_cache[loadbalancer_id]

    @property
    def default_discovery(self):
        discovery_resource = 'lb_pools'
        if self.lb_version == 'v2':
            discovery_resource = 'lb_loadbalancers'
        return discovery_resource

    @abc.abstractmethod
    def _get_sample(pool, c_data):
        """Return one Sample."""

    def get_samples(self, manager, cache, resources):
        if self.lb_version == 'v1':
            for pool in resources:
                try:
                    c_data = self._populate_stats_cache(pool['id'], cache)
                    yield self._get_sample(pool, c_data)
                except Exception:
                    LOG.exception('Ignoring pool %(pool_id)s',
                                  {'pool_id': pool['id']})
        elif self.lb_version == 'v2':
            for loadbalancer in resources:
                try:
                    c_data = self._populate_stats_cache_v2(loadbalancer['id'],
                                                           cache)
                    yield self._get_sample(loadbalancer, c_data)
                except Exception:
                    LOG.exception(
                        'Ignoring loadbalancer %(loadbalancer_id)s',
                        {'loadbalancer_id': loadbalancer['id']})


class LBActiveConnectionsPollster(_LBStatsPollster):
    """Pollster to capture Active Load Balancer connections."""

    @staticmethod
    def _get_sample(pool, data):
        return make_sample_from_pool(
            pool,
            name='network.services.lb.active.connections',
            type=sample.TYPE_GAUGE,
            unit='connection',
            volume=data.active_connections,
        )


class LBTotalConnectionsPollster(_LBStatsPollster):
    """Pollster to capture Total Load Balancer connections."""

    @staticmethod
    def _get_sample(pool, data):
        return make_sample_from_pool(
            pool,
            name='network.services.lb.total.connections',
            type=sample.TYPE_CUMULATIVE,
            unit='connection',
            volume=data.total_connections,
        )


class LBBytesInPollster(_LBStatsPollster):
    """Pollster to capture incoming bytes."""

    @staticmethod
    def _get_sample(pool, data):
        return make_sample_from_pool(
            pool,
            name='network.services.lb.incoming.bytes',
            type=sample.TYPE_GAUGE,
            unit='B',
            volume=data.bytes_in,
        )


class LBBytesOutPollster(_LBStatsPollster):
    """Pollster to capture outgoing bytes."""

    @staticmethod
    def _get_sample(pool, data):
        return make_sample_from_pool(
            pool,
            name='network.services.lb.outgoing.bytes',
            type=sample.TYPE_GAUGE,
            unit='B',
            volume=data.bytes_out,
        )


def make_sample_from_pool(pool, name, type, unit, volume,
                          resource_metadata=None):
    resource_metadata = resource_metadata or {}

    return sample.Sample(
        name=name,
        type=type,
        unit=unit,
        volume=volume,
        user_id=None,
        project_id=pool['tenant_id'],
        resource_id=pool['id'],
        resource_metadata=resource_metadata,
    )


class LBListenerPollster(BaseLBPollster):
    """Pollster to capture Load Balancer Listener status samples."""

    FIELDS = ['admin_state_up',
              'connection_limit',
              'description',
              'name',
              'default_pool_id',
              'protocol',
              'protocol_port',
              'operating_status',
              'loadbalancers'
              ]

    @property
    def default_discovery(self):
        return 'lb_listeners'

    def get_samples(self, manager, cache, resources):
        resources = resources or []

        for listener in resources:
            LOG.debug("Load Balancer Listener : %s" % listener)
            status = self.get_load_balancer_status_id(
                listener['operating_status'])
            if status == -1:
                # unknown status, skip this sample
                LOG.warning(_("Unknown status %(stat)s received on listener "
                              "%(id)s, skipping sample")
                            % {'stat': listener['operating_status'],
                               'id': listener['id']})
                continue

            yield sample.Sample(
                name='network.services.lb.listener',
                type=sample.TYPE_GAUGE,
                unit='listener',
                volume=status,
                user_id=None,
                project_id=listener['tenant_id'],
                resource_id=listener['id'],
                resource_metadata=self.extract_metadata(listener)
            )


class LBLoadBalancerPollster(BaseLBPollster):
    """Pollster to capture Load Balancer status samples."""

    FIELDS = ['admin_state_up',
              'description',
              'vip_address',
              'listeners',
              'name',
              'vip_subnet_id',
              'operating_status',
              ]

    @property
    def default_discovery(self):
        return 'lb_loadbalancers'

    def get_samples(self, manager, cache, resources):
        resources = resources or []

        for loadbalancer in resources:
            LOG.debug("Load Balancer: %s" % loadbalancer)
            status = self.get_load_balancer_status_id(
                loadbalancer['operating_status'])
            if status == -1:
                # unknown status, skip this sample
                LOG.warning(_("Unknown status %(stat)s received "
                              "on Load Balancer "
                              "%(id)s, skipping sample")
                            % {'stat': loadbalancer['operating_status'],
                               'id': loadbalancer['id']})
                continue

            yield sample.Sample(
                name='network.services.lb.loadbalancer',
                type=sample.TYPE_GAUGE,
                unit='loadbalancer',
                volume=status,
                user_id=None,
                project_id=loadbalancer['tenant_id'],
                resource_id=loadbalancer['id'],
                resource_metadata=self.extract_metadata(loadbalancer)
            )
