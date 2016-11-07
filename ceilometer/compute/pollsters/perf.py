# Copyright 2016 Intel
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
from ceilometer.i18n import _LE, _LW
from ceilometer import sample

LOG = log.getLogger(__name__)


PerfEventsData = collections.namedtuple('PerfEventsData',
                                        ['cpu_cycles', 'instructions',
                                         'cache_references', 'cache_misses'])


class _PerfEventsPollster(pollsters.BaseComputePollster):

    CACHE_KEY_MEMORY_BANDWIDTH = 'perf-events'

    def _populate_cache(self, inspector, cache, instance):
        i_cache = cache.setdefault(self.CACHE_KEY_MEMORY_BANDWIDTH, {})
        if instance.id not in i_cache:
            perf_events = self.inspector.inspect_perf_events(
                instance, self._inspection_duration)
            i_cache[instance.id] = PerfEventsData(
                perf_events.cpu_cycles,
                perf_events.instructions,
                perf_events.cache_references,
                perf_events.cache_misses,
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
                LOG.debug('Obtaining perf events is not implemented'
                          ' for %s', self.inspector.__class__.__name__)
            except Exception as err:
                LOG.exception(_LE('Could not get perf events for '
                                  '%(id)s: %(e)s'), {'id': instance.id,
                                                     'e': err})


class PerfEventsCPUCyclesPollster(_PerfEventsPollster):

    def _get_samples(self, instance, c_data):
        return self._get_sample_total_and_local(
            instance, 'perf.cpu.cycles', '', c_data, 'cpu_cycles')


class PerfEventsInstructionsPollster(_PerfEventsPollster):

    def _get_samples(self, instance, c_data):
        return self._get_sample_total_and_local(
            instance, 'perf.instructions', '', c_data, 'instructions')


class PerfEventsCacheReferencesPollster(_PerfEventsPollster):

    def _get_samples(self, instance, c_data):
        return self._get_sample_total_and_local(
            instance, 'perf.cache.references', '', c_data, 'cache_references')


class PerfEventsCacheMissesPollster(_PerfEventsPollster):

    def _get_samples(self, instance, c_data):
        return self._get_sample_total_and_local(
            instance, 'perf.cache.misses', '', c_data, 'cache_misses')
