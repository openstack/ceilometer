# -*- encoding: utf-8 -*-
#
# Copyright © 2012 eNovance <licensing@enovance.com>
# Copyright © 2012 Red Hat, Inc
#
# Author: Julien Danjou <julien@danjou.info>
# Author: Eoghan Glynn <eglynn@redhat.com>
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

import abc
import datetime

from ceilometer import counter
from ceilometer.compute import plugin
from ceilometer.compute.pollsters import util
from ceilometer.openstack.common import log

LOG = log.getLogger(__name__)


class _Base(plugin.ComputePollster):

    CACHE_KEY_CPU = 'cpu'

    def _get_cpu_info(self, inspector, instance_name, cache):
        i_cache = cache.setdefault(self.CACHE_KEY_CPU, {})
        if instance_name not in i_cache:
            i_cache[instance_name] = inspector.inspect_cpus(instance_name)
        return i_cache[instance_name]

    @abc.abstractmethod
    def _get_counter(instance, instance_name, cpu_info):
        """Return one Counter."""

    def get_counters(self, manager, cache, instance):
        LOG.info('checking instance %s', instance.id)
        instance_name = util.instance_name(instance)
        try:
            cpu_info = self._get_cpu_info(
                manager.inspector,
                instance_name,
                cache,
            )
            yield self._get_counter(
                instance,
                instance_name,
                cpu_info,
            )
        except Exception as err:
            LOG.error('could not get CPU time for %s: %s',
                      instance.id, err)
            LOG.exception(err)


class CPUPollster(_Base):

    @staticmethod
    def get_counter_names():
        return ['cpu']

    @staticmethod
    def _get_counter(instance, instance_name, cpu_info):
        LOG.info("CPUTIME USAGE: %s %d",
                 instance.__dict__, cpu_info.time)
        return util.make_counter_from_instance(
            instance,
            name='cpu',
            type=counter.TYPE_CUMULATIVE,
            unit='ns',
            volume=cpu_info.time,
        )


class CPUUtilPollster(_Base):
    # FIXME(eglynn): once we have a way of configuring which measures
    #                are published to each sink, we should by default
    #                disable publishing this derived measure to the
    #                metering store, only publishing to those sinks
    #                that specifically need it

    utilization_map = {}

    @staticmethod
    def get_counter_names():
        return ['cpu_util']

    def _get_cpu_util(self, instance, cpu_info):
        prev_times = self.utilization_map.get(instance.id)
        self.utilization_map[instance.id] = (cpu_info.time,
                                             datetime.datetime.now())
        cpu_util = 0.0
        if prev_times:
            prev_cpu = prev_times[0]
            prev_timestamp = prev_times[1]
            delta = self.utilization_map[instance.id][1] - prev_timestamp
            elapsed = (delta.seconds * (10 ** 6) + delta.microseconds) * 1000
            cores_fraction = 1.0 / cpu_info.number
            # account for cpu_time being reset when the instance is restarted
            time_used = (cpu_info.time - prev_cpu
                         if prev_cpu <= cpu_info.time else cpu_info.time)
            cpu_util = 100 * cores_fraction * time_used / elapsed
        return cpu_util

    def _get_counter(self, instance, instance_name, cpu_info):
        cpu_util = self._get_cpu_util(instance, cpu_info)
        LOG.info("CPU UTILIZATION %%: %s %0.2f",
                 instance.__dict__, cpu_util)
        return util.make_counter_from_instance(
            instance,
            name='cpu_util',
            type=counter.TYPE_GAUGE,
            unit='%',
            volume=cpu_util,
        )
