#
# Copyright 2014 Cisco Systems,Inc.
#
# Author: Pradeep Kilambi <pkilambi@cisco.com>
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
import six

from ceilometer import neutron_client
from ceilometer.openstack.common.gettextutils import _
from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils
from ceilometer import plugin
from ceilometer import sample

LOG = log.getLogger(__name__)

LBStatsData = collections.namedtuple(
    'LBStats',
    ['active_connections', 'total_connections', 'bytes_in', 'bytes_out']
)

# status map for converting metric status to volume int
STATUS = {
    'inactive': 0,
    'active': 1,
    'pending_create': 2,
}


class _BasePollster(plugin.PollsterBase):

    FIELDS = []
    nc = neutron_client.Client()

    def _iter_cache(self, cache, meter_name, method):
        if meter_name not in cache:
            cache[meter_name] = list(method())
        return iter(cache[meter_name])

    def extract_metadata(self, metric):
        return dict((k, metric[k]) for k in self.FIELDS)

    @staticmethod
    def get_status_id(value):
        status = value.lower()
        if status not in STATUS:
            return -1
        return STATUS[status]


class LBPoolPollster(_BasePollster):
    """Pollster to capture Load Balancer pool status samples.
    """
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

    def _get_lb_pools(self):
        return self.nc.pool_get_all()

    def get_samples(self, manager, cache, resources=None):
        for pool in self._iter_cache(cache, 'pool', self._get_lb_pools):
            LOG.debug("Load Balancer Pool : %s" % pool)
            status = self.get_status_id(pool['status'])
            if status == -1:
                # unknown status, skip this sample
                LOG.warn("Unknown status %s received on pool %s, "
                         "skipping sample" % (pool['status'], pool['id']))
                continue

            yield sample.Sample(
                name='network.services.lb.pool',
                type=sample.TYPE_GAUGE,
                unit='pool',
                volume=status,
                user_id=None,
                project_id=pool['tenant_id'],
                resource_id=pool['id'],
                timestamp=timeutils.utcnow().isoformat(),
                resource_metadata=self.extract_metadata(pool)
            )


class LBVipPollster(_BasePollster):
    """Pollster to capture Load Balancer Vip status samples.
    """
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

    def _get_lb_vips(self):
        return self.nc.vip_get_all()

    def get_samples(self, manager, cache, resources=None):
        for vip in self._iter_cache(cache, 'vip', self._get_lb_vips):
            LOG.debug("Load Balancer Vip : %s" % vip)
            status = self.get_status_id(vip['status'])
            if status == -1:
                # unknown status, skip this sample
                LOG.warn("Unknown status %s received on vip %s, "
                         "skipping sample" % (vip['status'], vip['id']))
                continue

            yield sample.Sample(
                name='network.services.lb.vip',
                type=sample.TYPE_GAUGE,
                unit='vip',
                volume=status,
                user_id=None,
                project_id=vip['tenant_id'],
                resource_id=vip['id'],
                timestamp=timeutils.utcnow().isoformat(),
                resource_metadata=self.extract_metadata(vip)
            )


class LBMemberPollster(_BasePollster):
    """Pollster to capture Load Balancer Member status samples.
    """
    FIELDS = ['admin_state_up',
              'address',
              'pool_id',
              'protocol_port',
              'status',
              'status_description',
              'weight',
              ]

    def _get_lb_members(self):
        return self.nc.member_get_all()

    def get_samples(self, manager, cache, resources=None):
        for member in self._iter_cache(cache, 'member', self._get_lb_members):
            LOG.debug("Load Balancer Member : %s" % member)
            status = self.get_status_id(member['status'])
            if status == -1:
                LOG.warn("Unknown status %s received on member %s, "
                         "skipping sample" % (member['status'], member['id']))
                continue
            yield sample.Sample(
                name='network.services.lb.member',
                type=sample.TYPE_GAUGE,
                unit='member',
                volume=status,
                user_id=None,
                project_id=member['tenant_id'],
                resource_id=member['id'],
                timestamp=timeutils.utcnow().isoformat(),
                resource_metadata=self.extract_metadata(member)
            )


class LBHealthMonitorPollster(_BasePollster):
    """Pollster to capture Load Balancer Health probes status samples.
    """
    FIELDS = ['admin_state_up',
              'delay',
              'max_retries',
              'pools',
              'timeout',
              'type'
              ]

    def _get_lb_health_probes(self):
        return self.nc.health_monitor_get_all()

    def get_samples(self, manager, cache, resources=None):
        for probe in self._iter_cache(cache, 'monitor',
                                      self._get_lb_health_probes):
            LOG.debug("Load Balancer Health probe : %s" % probe)
            yield sample.Sample(
                name='network.services.lb.health_monitor',
                type=sample.TYPE_GAUGE,
                unit='monitor',
                volume=1,
                user_id=None,
                project_id=probe['tenant_id'],
                resource_id=probe['id'],
                timestamp=timeutils.utcnow().isoformat(),
                resource_metadata=self.extract_metadata(probe)
            )


@six.add_metaclass(abc.ABCMeta)
class _LBStatsPollster(_BasePollster):
    """Base Statistics pollster capturing the statistics info
     and yielding samples for connections and bandwidth.
    """

    def _get_lb_pools(self):
        return self.nc.pool_get_all()

    def _get_pool_stats(self, pool_id):
        return self.nc.pool_stats(pool_id)

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
            timestamp=timeutils.isotime(),
            resource_metadata=resource_metadata,
        )

    def _populate_stats_cache(self, pool_id, cache):
        i_cache = cache.setdefault("lbstats", {})
        if pool_id not in i_cache:
            stats = self._get_pool_stats(pool_id)['stats']
            i_cache[pool_id] = LBStatsData(
                active_connections=stats['active_connections'],
                total_connections=stats['total_connections'],
                bytes_in=stats['bytes_in'],
                bytes_out=stats['bytes_out'],
            )
        return i_cache[pool_id]

    @abc.abstractmethod
    def _get_sample(pool, c_data):
        """Return one Sample."""

    def get_samples(self, manager, cache, resources=None):
        for pool in self._get_lb_pools():
            try:
                c_data = self._populate_stats_cache(pool['id'], cache)
                yield self._get_sample(pool, c_data)
            except Exception as err:
                LOG.exception(_('Ignoring pool %(pool_id)s: %(error)s'),
                              {'pool_id': pool['id'], 'error': err})


class LBActiveConnectionsPollster(_LBStatsPollster):
    """Pollster to capture Active Load Balancer connections.
    """

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
    """Pollster to capture Total Load Balancer connections
    """

    @staticmethod
    def _get_sample(pool, data):
        return make_sample_from_pool(
            pool,
            name='network.services.lb.total.connections',
            type=sample.TYPE_GAUGE,
            unit='connection',
            volume=data.total_connections,
        )


class LBBytesInPollster(_LBStatsPollster):
    """Pollster to capture incoming bytes.
    """

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
    """Pollster to capture outgoing bytes.
    """

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
        timestamp=timeutils.isotime(),
        resource_metadata=resource_metadata,
    )
