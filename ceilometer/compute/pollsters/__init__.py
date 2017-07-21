# Copyright 2014 Mirantis, Inc.
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

import collections

import monotonic
from oslo_log import log
from oslo_utils import timeutils

import ceilometer
from ceilometer.agent import plugin_base
from ceilometer.compute.pollsters import util
from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer import sample

LOG = log.getLogger(__name__)


class NoVolumeException(Exception):
    pass


class GenericComputePollster(plugin_base.PollsterBase):
    """This class aims to cache instance statistics data

    First polled pollsters that inherit of this will retrieve and cache
    stats of an instance, then other pollsters will just build the samples
    without queyring the backend anymore.
    """

    sample_name = None
    sample_unit = ''
    sample_type = sample.TYPE_GAUGE
    sample_stats_key = None
    inspector_method = None

    def setup_environment(self):
        super(GenericComputePollster, self).setup_environment()
        self.inspector = self._get_inspector(self.conf)

    @staticmethod
    def aggregate_method(stats):
        # Don't aggregate anything by default
        return stats

    @classmethod
    def _get_inspector(cls, conf):
        # FIXME(sileht): This doesn't looks threadsafe...
        try:
            inspector = cls._inspector
        except AttributeError:
            inspector = virt_inspector.get_hypervisor_inspector(conf)
            cls._inspector = inspector
        return inspector

    @property
    def default_discovery(self):
        return 'local_instances'

    def _record_poll_time(self):
        """Method records current time as the poll time.

        :return: time in seconds since the last poll time was recorded
        """
        current_time = timeutils.utcnow()
        duration = None
        if hasattr(self, '_last_poll_time'):
            duration = timeutils.delta_seconds(self._last_poll_time,
                                               current_time)
        self._last_poll_time = current_time
        return duration

    @staticmethod
    def get_additional_metadata(instance, stats):
        pass

    @staticmethod
    def get_resource_id(instance, stats):
        return instance.id

    def _inspect_cached(self, cache, instance, duration):
        cache.setdefault(self.inspector_method, {})
        if instance.id not in cache[self.inspector_method]:
            result = getattr(self.inspector, self.inspector_method)(
                instance, duration)
            polled_time = monotonic.monotonic()
            # Ensure we don't cache an iterator
            if isinstance(result, collections.Iterable):
                result = list(result)
            else:
                result = [result]
            cache[self.inspector_method][instance.id] = (polled_time, result)
        return cache[self.inspector_method][instance.id]

    def _stats_to_sample(self, instance, stats, polled_time):
        volume = getattr(stats, self.sample_stats_key)
        LOG.debug("%(instance_id)s/%(name)s volume: "
                  "%(volume)s" % {
                      'name': self.sample_name,
                      'instance_id': instance.id,
                      'volume': (volume if volume is not None
                                 else 'Unavailable')})

        if volume is None:
            raise NoVolumeException()

        return util.make_sample_from_instance(
            self.conf,
            instance,
            name=self.sample_name,
            unit=self.sample_unit,
            type=self.sample_type,
            resource_id=self.get_resource_id(instance, stats),
            volume=volume,
            additional_metadata=self.get_additional_metadata(
                instance, stats),
            monotonic_time=polled_time,
        )

    def get_samples(self, manager, cache, resources):
        self._inspection_duration = self._record_poll_time()
        for instance in resources:
            try:
                polled_time, result = self._inspect_cached(
                    cache, instance, self._inspection_duration)
                if not result:
                    continue
                for stats in self.aggregate_method(result):
                    yield self._stats_to_sample(instance, stats, polled_time)
            except NoVolumeException:
                # FIXME(sileht): This should be a removed... but I will
                # not change the test logic for now
                LOG.warning("%(name)s statistic in not available for "
                            "instance %(instance_id)s" %
                            {'name': self.sample_name,
                             'instance_id': instance.id})
            except virt_inspector.InstanceNotFoundException as err:
                # Instance was deleted while getting samples. Ignore it.
                LOG.debug('Exception while getting samples %s', err)
            except virt_inspector.InstanceShutOffException as e:
                LOG.debug('Instance %(instance_id)s was shut off while '
                          'getting sample of %(name)s: %(exc)s',
                          {'instance_id': instance.id,
                           'name': self.sample_name, 'exc': e})
            except virt_inspector.NoDataException as e:
                LOG.warning('Cannot inspect data of %(pollster)s for '
                            '%(instance_id)s, non-fatal reason: %(exc)s',
                            {'pollster': self.__class__.__name__,
                             'instance_id': instance.id, 'exc': e})
                raise plugin_base.PollsterPermanentError(resources)
            except ceilometer.NotImplementedError:
                # Selected inspector does not implement this pollster.
                LOG.debug('%(inspector)s does not provide data for '
                          '%(pollster)s',
                          {'inspector': self.inspector.__class__.__name__,
                           'pollster': self.__class__.__name__})
                raise plugin_base.PollsterPermanentError(resources)
            except Exception as err:
                LOG.error(
                    'Could not get %(name)s events for %(id)s: %(e)s', {
                        'name': self.sample_name, 'id': instance.id, 'e': err},
                    exc_info=True)
