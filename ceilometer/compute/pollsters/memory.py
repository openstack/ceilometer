# Copyright (c) 2014 VMware, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import abc
import collections

from oslo_log import log

import ceilometer
from ceilometer.agent import plugin_base
from ceilometer.compute import pollsters
from ceilometer.compute.pollsters import util
from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.i18n import _, _LE, _LW
from ceilometer import sample

LOG = log.getLogger(__name__)


MemoryBandwidthData = collections.namedtuple('MemoryBandwidthData',
                                             ['total', 'local'])


class MemoryUsagePollster(pollsters.BaseComputePollster):

    def get_samples(self, manager, cache, resources):
        self._inspection_duration = self._record_poll_time()
        for instance in resources:
            LOG.debug('Checking memory usage for instance %s', instance.id)
            try:
                memory_info = self.inspector.inspect_memory_usage(
                    instance, self._inspection_duration)
                LOG.debug("MEMORY USAGE: %(instance)s %(usage)f",
                          {'instance': instance,
                           'usage': memory_info.usage})
                yield util.make_sample_from_instance(
                    self.conf,
                    instance,
                    name='memory.usage',
                    type=sample.TYPE_GAUGE,
                    unit='MB',
                    volume=memory_info.usage,
                )
            except virt_inspector.InstanceNotFoundException as err:
                # Instance was deleted while getting samples. Ignore it.
                LOG.debug('Exception while getting samples %s', err)
            except virt_inspector.InstanceShutOffException as e:
                LOG.debug('Instance %(instance_id)s was shut off while '
                          'getting samples of %(pollster)s: %(exc)s',
                          {'instance_id': instance.id,
                           'pollster': self.__class__.__name__, 'exc': e})
            except virt_inspector.InstanceNoDataException as e:
                LOG.warning(_LW('Cannot inspect data of %(pollster)s for '
                                '%(instance_id)s, non-fatal reason: %(exc)s'),
                            {'pollster': self.__class__.__name__,
                             'instance_id': instance.id, 'exc': e})
            except virt_inspector.NoDataException as e:
                LOG.warning(_LW('Cannot inspect data of %(pollster)s for '
                                '%(instance_id)s: %(exc)s'),
                            {'pollster': self.__class__.__name__,
                             'instance_id': instance.id, 'exc': e})
                raise plugin_base.PollsterPermanentError(resources)
            except ceilometer.NotImplementedError:
                # Selected inspector does not implement this pollster.
                LOG.debug('Obtaining Memory Usage is not implemented for %s',
                          self.inspector.__class__.__name__)
                raise plugin_base.PollsterPermanentError(resources)
            except Exception as err:
                LOG.exception(_('Could not get Memory Usage for '
                                '%(id)s: %(e)s'), {'id': instance.id,
                                                   'e': err})


class MemoryResidentPollster(pollsters.BaseComputePollster):

    def get_samples(self, manager, cache, resources):
        self._inspection_duration = self._record_poll_time()
        for instance in resources:
            LOG.debug('Checking resident memory for instance %s',
                      instance.id)
            try:
                memory_info = self.inspector.inspect_memory_resident(
                    instance, self._inspection_duration)
                LOG.debug("RESIDENT MEMORY: %(instance)s %(resident)f",
                          {'instance': instance,
                           'resident': memory_info.resident})
                yield util.make_sample_from_instance(
                    self.conf,
                    instance,
                    name='memory.resident',
                    type=sample.TYPE_GAUGE,
                    unit='MB',
                    volume=memory_info.resident,
                )
            except virt_inspector.InstanceNotFoundException as err:
                # Instance was deleted while getting samples. Ignore it.
                LOG.debug('Exception while getting samples %s', err)
            except virt_inspector.InstanceShutOffException as e:
                LOG.debug('Instance %(instance_id)s was shut off while '
                          'getting samples of %(pollster)s: %(exc)s',
                          {'instance_id': instance.id,
                           'pollster': self.__class__.__name__, 'exc': e})
            except virt_inspector.NoDataException as e:
                LOG.warning(_LW('Cannot inspect data of %(pollster)s for '
                                '%(instance_id)s, non-fatal reason: %(exc)s'),
                            {'pollster': self.__class__.__name__,
                             'instance_id': instance.id, 'exc': e})
            except ceilometer.NotImplementedError:
                # Selected inspector does not implement this pollster.
                LOG.debug('Obtaining Resident Memory is not implemented'
                          ' for %s', self.inspector.__class__.__name__)
                raise plugin_base.PollsterPermanentError(resources)
            except Exception as err:
                LOG.exception(_LE('Could not get Resident Memory Usage for '
                                  '%(id)s: %(e)s'), {'id': instance.id,
                                                     'e': err})


class _MemoryBandwidthPollster(pollsters.BaseComputePollster):

    CACHE_KEY_MEMORY_BANDWIDTH = 'memory-bandwidth'

    def _populate_cache(self, inspector, cache, instance):
        i_cache = cache.setdefault(self.CACHE_KEY_MEMORY_BANDWIDTH, {})
        if instance.id not in i_cache:
            memory_bandwidth = self.inspector.inspect_memory_bandwidth(
                instance, self._inspection_duration)
            i_cache[instance.id] = MemoryBandwidthData(
                memory_bandwidth.total,
                memory_bandwidth.local,
            )
        return i_cache[instance.id]

    @abc.abstractmethod
    def _get_samples(self, instance, c_data):
        """Return one or more Samples."""

    def _get_sample_total_and_local(self, instance, _name, _unit,
                                    c_data, _element):
        """Total / local Pollster and return one Sample"""
        return [util.make_sample_from_instance(
            self.conf,
            instance,
            name=_name,
            type=sample.TYPE_GAUGE,
            unit=_unit,
            volume=getattr(c_data, _element),
        )]

    def get_samples(self, manager, cache, resources):
        self._inspection_duration = self._record_poll_time()
        for instance in resources:
            try:
                c_data = self._populate_cache(
                    self.inspector,
                    cache,
                    instance,
                )
                for s in self._get_samples(instance, c_data):
                    yield s
            except virt_inspector.InstanceNotFoundException as err:
                # Instance was deleted while getting samples. Ignore it.
                LOG.debug('Exception while getting samples %s', err)
            except virt_inspector.InstanceShutOffException as e:
                LOG.debug('Instance %(instance_id)s was shut off while '
                          'getting samples of %(pollster)s: %(exc)s',
                          {'instance_id': instance.id,
                           'pollster': self.__class__.__name__, 'exc': e})
            except virt_inspector.NoDataException as e:
                LOG.warning(_LW('Cannot inspect data of %(pollster)s for '
                                '%(instance_id)s, non-fatal reason: %(exc)s'),
                            {'pollster': self.__class__.__name__,
                             'instance_id': instance.id, 'exc': e})
                raise plugin_base.PollsterPermanentError(resources)
            except ceilometer.NotImplementedError:
                # Selected inspector does not implement this pollster.
                LOG.debug('Obtaining memory bandwidth is not implemented'
                          ' for %s', self.inspector.__class__.__name__)
            except Exception as err:
                LOG.exception(_LE('Could not get memory bandwidth for '
                                  '%(id)s: %(e)s'), {'id': instance.id,
                                                     'e': err})


class MemoryBandwidthTotalPollster(_MemoryBandwidthPollster):

    def _get_samples(self, instance, c_data):
        return self._get_sample_total_and_local(
            instance, 'memory.bandwidth.total', 'B/s', c_data, 'total')


class MemoryBandwidthLocalPollster(_MemoryBandwidthPollster):

    def _get_samples(self, instance, c_data):
        return self._get_sample_total_and_local(
            instance, 'memory.bandwidth.local', 'B/s', c_data, 'local')
