#
# Copyright 2012 eNovance <licensing@enovance.com>
# Copyright 2012 Red Hat, Inc
# Copyright 2014 Cisco Systems, Inc
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

from oslo_log import log
import six

import ceilometer
from ceilometer.compute import pollsters
from ceilometer.compute.pollsters import util
from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.i18n import _
from ceilometer import sample

LOG = log.getLogger(__name__)


DiskIOData = collections.namedtuple(
    'DiskIOData',
    'r_bytes r_requests w_bytes w_requests per_disk_requests',
)

DiskRateData = collections.namedtuple('DiskRateData',
                                      ['read_bytes_rate',
                                       'read_requests_rate',
                                       'write_bytes_rate',
                                       'write_requests_rate',
                                       'per_disk_rate'])

DiskLatencyData = collections.namedtuple('DiskLatencyData',
                                         ['disk_latency',
                                          'per_disk_latency'])

DiskIOPSData = collections.namedtuple('DiskIOPSData',
                                      ['iops_count',
                                       'per_disk_iops'])

DiskInfoData = collections.namedtuple('DiskInfoData',
                                      ['capacity',
                                       'allocation',
                                       'physical',
                                       'per_disk_info'])


@six.add_metaclass(abc.ABCMeta)
class _Base(pollsters.BaseComputePollster):

    DISKIO_USAGE_MESSAGE = ' '.join(["DISKIO USAGE:",
                                     "%s %s:",
                                     "read-requests=%d",
                                     "read-bytes=%d",
                                     "write-requests=%d",
                                     "write-bytes=%d",
                                     "errors=%d",
                                     ])

    CACHE_KEY_DISK = 'diskio'

    def _populate_cache(self, inspector, cache, instance):
        i_cache = cache.setdefault(self.CACHE_KEY_DISK, {})
        if instance.id not in i_cache:
            r_bytes = 0
            r_requests = 0
            w_bytes = 0
            w_requests = 0
            per_device_read_bytes = {}
            per_device_read_requests = {}
            per_device_write_bytes = {}
            per_device_write_requests = {}
            for disk, info in inspector.inspect_disks(instance):
                LOG.debug(self.DISKIO_USAGE_MESSAGE,
                          instance, disk.device, info.read_requests,
                          info.read_bytes, info.write_requests,
                          info.write_bytes, info.errors)
                r_bytes += info.read_bytes
                r_requests += info.read_requests
                w_bytes += info.write_bytes
                w_requests += info.write_requests
                # per disk data
                per_device_read_bytes[disk.device] = info.read_bytes
                per_device_read_requests[disk.device] = info.read_requests
                per_device_write_bytes[disk.device] = info.write_bytes
                per_device_write_requests[disk.device] = info.write_requests
            per_device_requests = {
                'read_bytes': per_device_read_bytes,
                'read_requests': per_device_read_requests,
                'write_bytes': per_device_write_bytes,
                'write_requests': per_device_write_requests,
            }
            i_cache[instance.id] = DiskIOData(
                r_bytes=r_bytes,
                r_requests=r_requests,
                w_bytes=w_bytes,
                w_requests=w_requests,
                per_disk_requests=per_device_requests,
            )
        return i_cache[instance.id]

    @abc.abstractmethod
    def _get_samples(instance, c_data):
        """Return one or more Sample."""

    @staticmethod
    def _get_sample_read_and_write(instance, _name, _unit, c_data,
                                   _volume, _metadata):
        """Read / write Pollster and return one Sample"""
        return [util.make_sample_from_instance(
            instance,
            name=_name,
            type=sample.TYPE_CUMULATIVE,
            unit=_unit,
            volume=getattr(c_data, _volume),
            additional_metadata={
                'device': c_data.per_disk_requests[_metadata].keys()},
        )]

    @staticmethod
    def _get_samples_per_device(c_data, _attr, instance, _name, _unit):
        """Return one or more Samples for meter 'disk.device.*'"""
        samples = []
        for disk, value in six.iteritems(c_data.per_disk_requests[_attr]):
            samples.append(util.make_sample_from_instance(
                instance,
                name=_name,
                type=sample.TYPE_CUMULATIVE,
                unit=_unit,
                volume=value,
                resource_id="%s-%s" % (instance.id, disk),
                additional_metadata={'disk_name': disk},
            ))
        return samples

    def get_samples(self, manager, cache, resources):
        for instance in resources:
            instance_name = util.instance_name(instance)
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
            except ceilometer.NotImplementedError:
                # Selected inspector does not implement this pollster.
                LOG.debug('%(inspector)s does not provide data for '
                          ' %(pollster)s',
                          {'inspector': self.inspector.__class__.__name__,
                           'pollster': self.__class__.__name__})
            except Exception as err:
                LOG.exception(_('Ignoring instance %(name)s: %(error)s'),
                              {'name': instance_name, 'error': err})


class ReadRequestsPollster(_Base):

    def _get_samples(self, instance, c_data):
        return self._get_sample_read_and_write(
            instance, 'disk.read.requests', 'request', c_data,
            'r_requests', 'read_requests')


class PerDeviceReadRequestsPollster(_Base):

    def _get_samples(self, instance, c_data):
        return self._get_samples_per_device(
            c_data, 'read_requests', instance,
            'disk.device.read.requests', 'request')


class ReadBytesPollster(_Base):

    def _get_samples(self, instance, c_data):
        return self._get_sample_read_and_write(
            instance, 'disk.read.bytes', 'B', c_data,
            'r_bytes', 'read_bytes')


class PerDeviceReadBytesPollster(_Base):

    def _get_samples(self, instance, c_data):
        return self._get_samples_per_device(
            c_data, 'read_bytes', instance,
            'disk.device.read.bytes', 'B')


class WriteRequestsPollster(_Base):

    def _get_samples(self, instance, c_data):
        return self._get_sample_read_and_write(
            instance, 'disk.write.requests', 'request',
            c_data, 'w_requests', 'write_requests')


class PerDeviceWriteRequestsPollster(_Base):

    def _get_samples(self, instance, c_data):
        return self._get_samples_per_device(
            c_data, 'write_requests', instance,
            'disk.device.write.requests', 'request')


class WriteBytesPollster(_Base):

    def _get_samples(self, instance, c_data):
        return self._get_sample_read_and_write(
            instance, 'disk.write.bytes', 'B',
            c_data, 'w_bytes', 'write_bytes')


class PerDeviceWriteBytesPollster(_Base):

    def _get_samples(self, instance, c_data):
        return self._get_samples_per_device(
            c_data, 'write_bytes', instance,
            'disk.device.write.bytes', 'B')


@six.add_metaclass(abc.ABCMeta)
class _DiskRatesPollsterBase(pollsters.BaseComputePollster):

    CACHE_KEY_DISK_RATE = 'diskio-rate'

    def _populate_cache(self, inspector, cache, instance):
        i_cache = cache.setdefault(self.CACHE_KEY_DISK_RATE, {})
        if instance.id not in i_cache:
            r_bytes_rate = 0
            r_requests_rate = 0
            w_bytes_rate = 0
            w_requests_rate = 0
            per_disk_r_bytes_rate = {}
            per_disk_r_requests_rate = {}
            per_disk_w_bytes_rate = {}
            per_disk_w_requests_rate = {}
            disk_rates = inspector.inspect_disk_rates(
                instance, self._inspection_duration)
            for disk, info in disk_rates:
                r_bytes_rate += info.read_bytes_rate
                r_requests_rate += info.read_requests_rate
                w_bytes_rate += info.write_bytes_rate
                w_requests_rate += info.write_requests_rate

                per_disk_r_bytes_rate[disk.device] = info.read_bytes_rate
                per_disk_r_requests_rate[disk.device] = info.read_requests_rate
                per_disk_w_bytes_rate[disk.device] = info.write_bytes_rate
                per_disk_w_requests_rate[disk.device] = (
                    info.write_requests_rate)
            per_disk_rate = {
                'read_bytes_rate': per_disk_r_bytes_rate,
                'read_requests_rate': per_disk_r_requests_rate,
                'write_bytes_rate': per_disk_w_bytes_rate,
                'write_requests_rate': per_disk_w_requests_rate,
            }
            i_cache[instance.id] = DiskRateData(
                r_bytes_rate,
                r_requests_rate,
                w_bytes_rate,
                w_requests_rate,
                per_disk_rate
            )
        return i_cache[instance.id]

    @abc.abstractmethod
    def _get_samples(self, instance, disk_rates_info):
        """Return one or more Sample."""

    def get_samples(self, manager, cache, resources):
        self._inspection_duration = self._record_poll_time()
        for instance in resources:
            try:
                disk_rates_info = self._populate_cache(
                    self.inspector,
                    cache,
                    instance,
                )
                for disk_rate in self._get_samples(instance, disk_rates_info):
                    yield disk_rate
            except virt_inspector.InstanceNotFoundException as err:
                # Instance was deleted while getting samples. Ignore it.
                LOG.debug('Exception while getting samples %s', err)
            except ceilometer.NotImplementedError:
                # Selected inspector does not implement this pollster.
                LOG.debug('%(inspector)s does not provide data for '
                          ' %(pollster)s',
                          {'inspector': self.inspector.__class__.__name__,
                           'pollster': self.__class__.__name__})
            except Exception as err:
                instance_name = util.instance_name(instance)
                LOG.exception(_('Ignoring instance %(name)s: %(error)s'),
                              {'name': instance_name, 'error': err})

    def _get_samples_per_device(self, disk_rates_info, _attr, instance,
                                _name, _unit):
        """Return one or more Samples for meter 'disk.device.*'."""
        samples = []
        for disk, value in six.iteritems(disk_rates_info.per_disk_rate[
                _attr]):
            samples.append(util.make_sample_from_instance(
                instance,
                name=_name,
                type=sample.TYPE_GAUGE,
                unit=_unit,
                volume=value,
                resource_id="%s-%s" % (instance.id, disk),
                additional_metadata={'disk_name': disk},
            ))
        return samples

    def _get_sample_read_and_write(self, instance, _name, _unit, _element,
                                   _attr1, _attr2):
        """Read / write Pollster and return one Sample"""
        return [util.make_sample_from_instance(
            instance,
            name=_name,
            type=sample.TYPE_GAUGE,
            unit=_unit,
            volume=getattr(_element, _attr1),
            additional_metadata={
                'device': getattr(_element, _attr2)[_attr1].keys()},
        )]


class ReadBytesRatePollster(_DiskRatesPollsterBase):

    def _get_samples(self, instance, disk_rates_info):
        return self._get_sample_read_and_write(
            instance, 'disk.read.bytes.rate', 'B/s', disk_rates_info,
            'read_bytes_rate', 'per_disk_rate')


class PerDeviceReadBytesRatePollster(_DiskRatesPollsterBase):

    def _get_samples(self, instance, disk_rates_info):
        return self._get_samples_per_device(
            disk_rates_info, 'read_bytes_rate', instance,
            'disk.device.read.bytes.rate', 'B/s')


class ReadRequestsRatePollster(_DiskRatesPollsterBase):

    def _get_samples(self, instance, disk_rates_info):
        return self._get_sample_read_and_write(
            instance, 'disk.read.requests.rate', 'requests/s', disk_rates_info,
            'read_requests_rate', 'per_disk_rate')


class PerDeviceReadRequestsRatePollster(_DiskRatesPollsterBase):

    def _get_samples(self, instance, disk_rates_info):
        return self._get_samples_per_device(
            disk_rates_info, 'read_requests_rate', instance,
            'disk.device.read.requests.rate', 'requests/s')


class WriteBytesRatePollster(_DiskRatesPollsterBase):

    def _get_samples(self, instance, disk_rates_info):
        return self._get_sample_read_and_write(
            instance, 'disk.write.bytes.rate', 'B/s', disk_rates_info,
            'write_bytes_rate', 'per_disk_rate')


class PerDeviceWriteBytesRatePollster(_DiskRatesPollsterBase):

    def _get_samples(self, instance, disk_rates_info):
        return self._get_samples_per_device(
            disk_rates_info, 'write_bytes_rate', instance,
            'disk.device.write.bytes.rate', 'B/s')


class WriteRequestsRatePollster(_DiskRatesPollsterBase):

    def _get_samples(self, instance, disk_rates_info):
        return self._get_sample_read_and_write(
            instance, 'disk.write.requests.rate', 'requests/s',
            disk_rates_info, 'write_requests_rate', 'per_disk_rate')


class PerDeviceWriteRequestsRatePollster(_DiskRatesPollsterBase):

    def _get_samples(self, instance, disk_rates_info):
        return self._get_samples_per_device(
            disk_rates_info, 'write_requests_rate', instance,
            'disk.device.write.requests.rate', 'requests/s')


@six.add_metaclass(abc.ABCMeta)
class _DiskLatencyPollsterBase(pollsters.BaseComputePollster):

    CACHE_KEY_DISK_LATENCY = 'disk-latency'

    def _populate_cache(self, inspector, cache, instance):
        return self._populate_cache_create(
            cache.setdefault(self.CACHE_KEY_DISK_LATENCY, {}),
            instance, inspector, DiskLatencyData,
            'inspect_disk_latency', 'disk_latency')

    @abc.abstractmethod
    def _get_samples(self, instance, disk_rates_info):
        """Return one or more Sample."""

    def get_samples(self, manager, cache, resources):
        for instance in resources:
            try:
                disk_latency_info = self._populate_cache(
                    self.inspector,
                    cache,
                    instance,
                )
                for disk_latency in self._get_samples(instance,
                                                      disk_latency_info):
                    yield disk_latency
            except virt_inspector.InstanceNotFoundException as err:
                # Instance was deleted while getting samples. Ignore it.
                LOG.debug('Exception while getting samples %s', err)
            except ceilometer.NotImplementedError:
                # Selected inspector does not implement this pollster.
                LOG.debug('%(inspector)s does not provide data for '
                          ' %(pollster)s',
                          {'inspector': self.inspector.__class__.__name__,
                           'pollster': self.__class__.__name__})
            except Exception as err:
                instance_name = util.instance_name(instance)
                LOG.exception(_('Ignoring instance %(name)s: %(error)s'),
                              {'name': instance_name, 'error': err})


class DiskLatencyPollster(_DiskLatencyPollsterBase):

    def _get_samples(self, instance, disk_latency_info):
        return [util.make_sample_from_instance(
            instance,
            name='disk.latency',
            type=sample.TYPE_GAUGE,
            unit='ms',
            volume=disk_latency_info.disk_latency / 1000
        )]


class PerDeviceDiskLatencyPollster(_DiskLatencyPollsterBase):

    def _get_samples(self, instance, disk_latency_info):
        samples = []
        for disk, value in six.iteritems(disk_latency_info.per_disk_latency[
                'disk_latency']):
            samples.append(util.make_sample_from_instance(
                instance,
                name='disk.device.latency',
                type=sample.TYPE_GAUGE,
                unit='ms',
                volume=value / 1000,
                resource_id="%s-%s" % (instance.id, disk),
                additional_metadata={'disk_name': disk},
            ))
        return samples


class _DiskIOPSPollsterBase(pollsters.BaseComputePollster):

    CACHE_KEY_DISK_IOPS = 'disk-iops'

    def _populate_cache(self, inspector, cache, instance):
        return self._populate_cache_create(
            cache.setdefault(self.CACHE_KEY_DISK_IOPS, {}),
            instance, inspector, DiskIOPSData,
            'inspect_disk_iops', 'iops_count')

    @abc.abstractmethod
    def _get_samples(self, instance, disk_rates_info):
        """Return one or more Sample."""

    def get_samples(self, manager, cache, resources):
        for instance in resources:
            try:
                disk_iops_info = self._populate_cache(
                    self.inspector,
                    cache,
                    instance,
                )
                for disk_iops in self._get_samples(instance,
                                                   disk_iops_info):
                    yield disk_iops
            except virt_inspector.InstanceNotFoundException as err:
                # Instance was deleted while getting samples. Ignore it.
                LOG.debug('Exception while getting samples %s', err)
            except ceilometer.NotImplementedError:
                # Selected inspector does not implement this pollster.
                LOG.debug('%(inspector)s does not provide data for '
                          '%(pollster)s',
                          {'inspector': self.inspector.__class__.__name__,
                           'pollster': self.__class__.__name__})
            except Exception as err:
                instance_name = util.instance_name(instance)
                LOG.exception(_('Ignoring instance %(name)s: %(error)s'),
                              {'name': instance_name, 'error': err})


class DiskIOPSPollster(_DiskIOPSPollsterBase):

    def _get_samples(self, instance, disk_iops_info):
        return [util.make_sample_from_instance(
            instance,
            name='disk.iops',
            type=sample.TYPE_GAUGE,
            unit='count/s',
            volume=disk_iops_info.iops_count
        )]


class PerDeviceDiskIOPSPollster(_DiskIOPSPollsterBase):

    def _get_samples(self, instance, disk_iops_info):
        samples = []
        for disk, value in six.iteritems(disk_iops_info.per_disk_iops[
                'iops_count']):
            samples.append(util.make_sample_from_instance(
                instance,
                name='disk.device.iops',
                type=sample.TYPE_GAUGE,
                unit='count/s',
                volume=value,
                resource_id="%s-%s" % (instance.id, disk),
                additional_metadata={'disk_name': disk},
            ))
        return samples


@six.add_metaclass(abc.ABCMeta)
class _DiskInfoPollsterBase(pollsters.BaseComputePollster):

    CACHE_KEY_DISK_INFO = 'diskinfo'

    def _populate_cache(self, inspector, cache, instance):
        i_cache = cache.setdefault(self.CACHE_KEY_DISK_INFO, {})
        if instance.id not in i_cache:
            all_capacity = 0
            all_allocation = 0
            all_physical = 0
            per_disk_capacity = {}
            per_disk_allocation = {}
            per_disk_physical = {}
            disk_info = inspector.inspect_disk_info(
                instance)
            for disk, info in disk_info:
                all_capacity += info.capacity
                all_allocation += info.allocation
                all_physical += info.physical

                per_disk_capacity[disk.device] = info.capacity
                per_disk_allocation[disk.device] = info.allocation
                per_disk_physical[disk.device] = info.physical
            per_disk_info = {
                'capacity': per_disk_capacity,
                'allocation': per_disk_allocation,
                'physical': per_disk_physical,
            }
            i_cache[instance.id] = DiskInfoData(
                all_capacity,
                all_allocation,
                all_physical,
                per_disk_info
            )
        return i_cache[instance.id]

    @abc.abstractmethod
    def _get_samples(self, instance, disk_info):
        """Return one or more Sample."""

    def _get_samples_per_device(self, disk_info, _attr, instance, _name):
        """Return one or more Samples for meter 'disk.device.*'."""
        samples = []
        for disk, value in six.iteritems(disk_info.per_disk_info[_attr]):
            samples.append(util.make_sample_from_instance(
                instance,
                name=_name,
                type=sample.TYPE_GAUGE,
                unit='B',
                volume=value,
                resource_id="%s-%s" % (instance.id, disk),
                additional_metadata={'disk_name': disk},
            ))
        return samples

    def _get_samples_task(self, instance, _name, disk_info, _attr1, _attr2):
        """Return one or more Samples for meter 'disk.task.*'."""
        return [util.make_sample_from_instance(
            instance,
            name=_name,
            type=sample.TYPE_GAUGE,
            unit='B',
            volume=getattr(disk_info, _attr1),
            additional_metadata={
                'device': disk_info.per_disk_info[_attr2].keys()},
        )]

    def get_samples(self, manager, cache, resources):
        for instance in resources:
            try:
                disk_size_info = self._populate_cache(
                    self.inspector,
                    cache,
                    instance,
                )
                for disk_info in self._get_samples(instance, disk_size_info):
                    yield disk_info
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
                LOG.debug('%(inspector)s does not provide data for '
                          ' %(pollster)s',
                          {'inspector': self.inspector.__class__.__name__,
                           'pollster': self.__class__.__name__})
            except Exception as err:
                instance_name = util.instance_name(instance)
                LOG.exception(_('Ignoring instance %(name)s '
                                '(%(instance_id)s) : %(error)s') % (
                              {'name': instance_name,
                               'instance_id': instance.id,
                               'error': err}))


class CapacityPollster(_DiskInfoPollsterBase):

    def _get_samples(self, instance, disk_info):
        return self._get_samples_task(
            instance, 'disk.capacity', disk_info,
            'capacity', 'capacity')


class PerDeviceCapacityPollster(_DiskInfoPollsterBase):

    def _get_samples(self, instance, disk_info):
        return self._get_samples_per_device(
            disk_info, 'capacity', instance, 'disk.device.capacity')


class AllocationPollster(_DiskInfoPollsterBase):

    def _get_samples(self, instance, disk_info):
        return self._get_samples_task(
            instance, 'disk.allocation', disk_info,
            'allocation', 'allocation')


class PerDeviceAllocationPollster(_DiskInfoPollsterBase):

    def _get_samples(self, instance, disk_info):
        return self._get_samples_per_device(
            disk_info, 'allocation', instance, 'disk.device.allocation')


class PhysicalPollster(_DiskInfoPollsterBase):

    def _get_samples(self, instance, disk_info):
        return self._get_samples_task(
            instance, 'disk.usage', disk_info,
            'physical', 'physical')


class PerDevicePhysicalPollster(_DiskInfoPollsterBase):

    def _get_samples(self, instance, disk_info):
        return self._get_samples_per_device(
            disk_info, 'physical', instance, 'disk.device.usage')
