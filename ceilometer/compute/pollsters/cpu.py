#
# Copyright 2012 eNovance <licensing@enovance.com>
# Copyright 2012 Red Hat, Inc
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


import monotonic
from oslo_log import log

import ceilometer
from ceilometer.agent import plugin_base
from ceilometer.compute import pollsters
from ceilometer.compute.pollsters import util
from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.i18n import _
from ceilometer import sample

LOG = log.getLogger(__name__)


class CPUPollster(pollsters.BaseComputePollster):

    def get_samples(self, manager, cache, resources):
        for instance in resources:
            LOG.debug('checking instance %s', instance.id)
            try:
                cpu_info = self.inspector.inspect_cpus(instance)
                LOG.debug("CPUTIME USAGE: %(instance)s %(time)d",
                          {'instance': instance,
                           'time': cpu_info.time})
                cpu_num = {'cpu_number': cpu_info.number}
                yield util.make_sample_from_instance(
                    self.conf,
                    instance,
                    name='cpu',
                    type=sample.TYPE_CUMULATIVE,
                    unit='ns',
                    volume=cpu_info.time,
                    additional_metadata=cpu_num,
                    monotonic_time=monotonic.monotonic()
                )
            except virt_inspector.InstanceNotFoundException as err:
                # Instance was deleted while getting samples. Ignore it.
                LOG.debug('Exception while getting samples %s', err)
            except virt_inspector.InstanceShutOffException as e:
                LOG.debug('Instance %(instance_id)s was shut off while '
                          'getting samples of %(pollster)s: %(exc)s',
                          {'instance_id': instance.id,
                           'pollster': self.__class__.__name__, 'exc': e})
            except ceilometer.NotImplementedError:
                # Selected inspector does not implement this pollster.
                LOG.debug('Obtaining CPU time is not implemented for %s',
                          self.inspector.__class__.__name__)
                raise plugin_base.PollsterPermanentError(resources)
            except Exception as err:
                LOG.exception(_('could not get CPU time for %(id)s: %(e)s'),
                              {'id': instance.id, 'e': err})


class CPUUtilPollster(pollsters.BaseComputePollster):

    def get_samples(self, manager, cache, resources):
        self._inspection_duration = self._record_poll_time()
        for instance in resources:
            LOG.debug('Checking CPU util for instance %s', instance.id)
            try:
                cpu_info = self.inspector.inspect_cpu_util(
                    instance, self._inspection_duration)
                LOG.debug("CPU UTIL: %(instance)s %(util)d",
                          {'instance': instance,
                           'util': cpu_info.util})
                yield util.make_sample_from_instance(
                    self.conf,
                    instance,
                    name='cpu_util',
                    type=sample.TYPE_GAUGE,
                    unit='%',
                    volume=cpu_info.util,
                )
            except virt_inspector.InstanceNotFoundException as err:
                # Instance was deleted while getting samples. Ignore it.
                LOG.debug('Exception while getting samples %s', err)
            except ceilometer.NotImplementedError:
                # Selected inspector does not implement this pollster.
                LOG.debug('Obtaining CPU Util is not implemented for %s',
                          self.inspector.__class__.__name__)
                raise plugin_base.PollsterPermanentError(resources)
            except Exception as err:
                LOG.exception(_('Could not get CPU Util for %(id)s: %(e)s'),
                              {'id': instance.id, 'e': err})


class CPUL3CachePollster(pollsters.BaseComputePollster):

    def get_samples(self, manager, cache, resources):
        for instance in resources:
            LOG.debug(_('checking cache usage for instance %s'), instance.id)
            try:
                cpu_cache = self.inspector.inspect_cpu_l3_cache(instance)
                LOG.debug(_("CPU cache size: %(id)s %(cache_size)d"),
                          ({'id': instance.id,
                            'cache_size': cpu_cache.l3_cache_usage}))
                yield util.make_sample_from_instance(
                    self.conf,
                    instance,
                    name='cpu_l3_cache',
                    type=sample.TYPE_GAUGE,
                    unit='B',
                    volume=cpu_cache.l3_cache_usage,
                )
            except virt_inspector.InstanceNotFoundException as err:
                # Instance was deleted while getting samples. Ignore it.
                LOG.debug('Exception while getting samples %s', err)
            except virt_inspector.NoDataException as e:
                LOG.warning(('Cannot inspect data of %(pollster)s for '
                             '%(instance_id)s, non-fatal reason: %(exc)s'),
                            {'pollster': self.__class__.__name__,
                             'instance_id': instance.id, 'exc': e})
                raise plugin_base.PollsterPermanentError(resources)
            except ceilometer.NotImplementedError:
                # Selected inspector does not implement this pollster.
                LOG.debug('Obtaining cache usage is not implemented for %s',
                          self.inspector.__class__.__name__)
                raise plugin_base.PollsterPermanentError(resources)
            except Exception as err:
                LOG.exception(_('Could not get cache usage for %(id)s: %(e)s'),
                              {'id': instance.id, 'e': err})
