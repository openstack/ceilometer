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

from oslo_log import log

import ceilometer
from ceilometer.compute import pollsters
from ceilometer.compute.pollsters import util
from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.i18n import _, _LE, _LW
from ceilometer import sample

LOG = log.getLogger(__name__)


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
            except virt_inspector.NoDataException as e:
                LOG.warning(_LW('Cannot inspect data of %(pollster)s for '
                                '%(instance_id)s, non-fatal reason: %(exc)s'),
                            {'pollster': self.__class__.__name__,
                             'instance_id': instance.id, 'exc': e})
            except ceilometer.NotImplementedError:
                # Selected inspector does not implement this pollster.
                LOG.debug('Obtaining Memory Usage is not implemented for %s',
                          self.inspector.__class__.__name__)
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
            except Exception as err:
                LOG.exception(_LE('Could not get Resident Memory Usage for '
                                  '%(id)s: %(e)s'), {'id': instance.id,
                                                     'e': err})
