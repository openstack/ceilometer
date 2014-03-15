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
import collections

import six

from ceilometer.compute import plugin
from ceilometer.compute.pollsters import util
from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log
from ceilometer import sample

LOG = log.getLogger(__name__)


DiskIOData = collections.namedtuple(
    'DiskIOData',
    'r_bytes r_requests w_bytes w_requests',
)


@six.add_metaclass(abc.ABCMeta)
class _Base(plugin.ComputePollster):

    DISKIO_USAGE_MESSAGE = ' '.join(["DISKIO USAGE:",
                                     "%s %s:",
                                     "read-requests=%d",
                                     "read-bytes=%d",
                                     "write-requests=%d",
                                     "write-bytes=%d",
                                     "errors=%d",
                                     ])

    CACHE_KEY_DISK = 'diskio'

    def _populate_cache(self, inspector, cache, instance, instance_name):
        i_cache = cache.setdefault(self.CACHE_KEY_DISK, {})
        if instance_name not in i_cache:
            r_bytes = 0
            r_requests = 0
            w_bytes = 0
            w_requests = 0
            for disk, info in inspector.inspect_disks(instance_name):
                LOG.info(self.DISKIO_USAGE_MESSAGE,
                         instance, disk.device, info.read_requests,
                         info.read_bytes, info.write_requests,
                         info.write_bytes, info.errors)
                r_bytes += info.read_bytes
                r_requests += info.read_requests
                w_bytes += info.write_bytes
                w_requests += info.write_requests
            i_cache[instance_name] = DiskIOData(
                r_bytes=r_bytes,
                r_requests=r_requests,
                w_bytes=w_bytes,
                w_requests=w_requests,
            )
        return i_cache[instance_name]

    @abc.abstractmethod
    def _get_sample(instance, c_data):
        """Return one Sample."""

    def get_samples(self, manager, cache, resources):
        for instance in resources:
            instance_name = util.instance_name(instance)
            try:
                c_data = self._populate_cache(
                    manager.inspector,
                    cache,
                    instance,
                    instance_name,
                )
                yield self._get_sample(instance, c_data)
            except virt_inspector.InstanceNotFoundException as err:
                # Instance was deleted while getting samples. Ignore it.
                LOG.debug(_('Exception while getting samples %s'), err)
            except NotImplementedError:
                # Selected inspector does not implement this pollster.
                LOG.debug(_('%(inspector)s does not provide data for '
                            ' %(pollster)s'), ({
                          'inspector': manager.inspector.__class__.__name__,
                          'pollster': self.__class__.__name__}))
            except Exception as err:
                LOG.warning(_('Ignoring instance %(name)s: %(error)s') % (
                            {'name': instance_name, 'error': err}))
                LOG.exception(err)


class ReadRequestsPollster(_Base):

    @staticmethod
    def _get_sample(instance, c_data):
        return util.make_sample_from_instance(
            instance,
            name='disk.read.requests',
            type=sample.TYPE_CUMULATIVE,
            unit='request',
            volume=c_data.r_requests,
        )


class ReadBytesPollster(_Base):

    @staticmethod
    def _get_sample(instance, c_data):
        return util.make_sample_from_instance(
            instance,
            name='disk.read.bytes',
            type=sample.TYPE_CUMULATIVE,
            unit='B',
            volume=c_data.r_bytes,
        )


class WriteRequestsPollster(_Base):

    @staticmethod
    def _get_sample(instance, c_data):
        return util.make_sample_from_instance(
            instance,
            name='disk.write.requests',
            type=sample.TYPE_CUMULATIVE,
            unit='request',
            volume=c_data.w_requests,
        )


class WriteBytesPollster(_Base):

    @staticmethod
    def _get_sample(instance, c_data):
        return util.make_sample_from_instance(
            instance,
            name='disk.write.bytes',
            type=sample.TYPE_CUMULATIVE,
            unit='B',
            volume=c_data.w_bytes,
        )


@six.add_metaclass(abc.ABCMeta)
class _DiskRatesPollsterBase(plugin.ComputePollster):

    CACHE_KEY_DISK_RATE = 'diskio-rate'

    def _populate_cache(self, inspector, cache, instance):
        i_cache = cache.setdefault(self.CACHE_KEY_DISK_RATE, {})
        if instance.id not in i_cache:
            r_bytes_rate = 0
            r_requests_rate = 0
            w_bytes_rate = 0
            w_requests_rate = 0
            disk_rates = inspector.inspect_disk_rates(
                instance, self._inspection_duration)
            for disk, info in disk_rates:
                r_bytes_rate += info.read_bytes_rate
                r_requests_rate += info.read_requests_rate
                w_bytes_rate += info.write_bytes_rate
                w_requests_rate += info.write_requests_rate
            i_cache[instance.id] = virt_inspector.DiskRateStats(
                r_bytes_rate,
                r_requests_rate,
                w_bytes_rate,
                w_requests_rate
            )
        return i_cache[instance.id]

    @abc.abstractmethod
    def _get_sample(self, instance, disk_rates_info):
        """Return one Sample."""

    def get_samples(self, manager, cache, resources):
        self._inspection_duration = self._record_poll_time()
        for instance in resources:
            try:
                disk_rates_info = self._populate_cache(
                    manager.inspector,
                    cache,
                    instance,
                )
                yield self._get_sample(instance, disk_rates_info)
            except virt_inspector.InstanceNotFoundException as err:
                # Instance was deleted while getting samples. Ignore it.
                LOG.debug(_('Exception while getting samples %s'), err)
            except NotImplementedError:
                # Selected inspector does not implement this pollster.
                LOG.debug(_('%(inspector)s does not provide data for '
                            ' %(pollster)s'), ({
                          'inspector': manager.inspector.__class__.__name__,
                          'pollster': self.__class__.__name__}))
            except Exception as err:
                instance_name = util.instance_name(instance)
                LOG.error(_('Ignoring instance %(name)s: %(error)s') % (
                    {'name': instance_name, 'error': err}))


class ReadBytesRatePollster(_DiskRatesPollsterBase):

    def _get_sample(self, instance, disk_rates_info):
        return util.make_sample_from_instance(
            instance,
            name='disk.read.bytes.rate',
            type=sample.TYPE_GAUGE,
            unit='B/s',
            volume=disk_rates_info.read_bytes_rate,
        )


class ReadRequestsRatePollster(_DiskRatesPollsterBase):

    def _get_sample(self, instance, disk_rates_info):
        return util.make_sample_from_instance(
            instance,
            name='disk.read.requests.rate',
            type=sample.TYPE_GAUGE,
            unit='requests/s',
            volume=disk_rates_info.read_requests_rate,
        )


class WriteBytesRatePollster(_DiskRatesPollsterBase):

    def _get_sample(self, instance, disk_rates_info):
        return util.make_sample_from_instance(
            instance,
            name='disk.write.bytes.rate',
            type=sample.TYPE_GAUGE,
            unit='B/s',
            volume=disk_rates_info.write_bytes_rate,
        )


class WriteRequestsRatePollster(_DiskRatesPollsterBase):

    def _get_sample(self, instance, disk_rates_info):
        return util.make_sample_from_instance(
            instance,
            name='disk.write.requests.rate',
            type=sample.TYPE_GAUGE,
            unit='requests/s',
            volume=disk_rates_info.write_requests_rate,
        )
