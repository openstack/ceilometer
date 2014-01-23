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

    def get_samples(self, manager, cache, instance):
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
