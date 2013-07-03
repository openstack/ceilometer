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

import copy

from ceilometer import counter
from ceilometer.compute import plugin
from ceilometer.compute.pollsters import util
from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils

LOG = log.getLogger(__name__)


class _Base(plugin.ComputePollster):

    NET_USAGE_MESSAGE = ' '.join(["NETWORK USAGE:", "%s %s:", "read-bytes=%d",
                                  "write-bytes=%d"])

    @staticmethod
    def make_vnic_counter(instance, name, type, unit, volume, vnic_data):
        metadata = copy.copy(vnic_data)
        resource_metadata = dict(zip(metadata._fields, metadata))
        resource_metadata['instance_id'] = instance.id
        resource_metadata['instance_type'] = \
            instance.flavor['id'] if instance.flavor else None

        if vnic_data.fref is not None:
            rid = vnic_data.fref
        else:
            instance_name = util.instance_name(instance)
            rid = "%s-%s-%s" % (instance_name, instance.id, vnic_data.name)

        return counter.Counter(
            name=name,
            type=type,
            unit=unit,
            volume=volume,
            user_id=instance.user_id,
            project_id=instance.tenant_id,
            resource_id=rid,
            timestamp=timeutils.isotime(),
            resource_metadata=resource_metadata
        )

    CACHE_KEY_VNIC = 'vnics'

    def _get_vnics_for_instance(self, cache, inspector, instance_name):
        i_cache = cache.setdefault(self.CACHE_KEY_VNIC, {})
        if instance_name not in i_cache:
            i_cache[instance_name] = list(
                inspector.inspect_vnics(instance_name)
            )
        return i_cache[instance_name]

    def get_counters(self, manager, cache, instance):
        instance_name = util.instance_name(instance)
        LOG.info('checking instance %s', instance.id)
        try:
            vnics = self._get_vnics_for_instance(
                cache,
                manager.inspector,
                instance_name,
            )
            for vnic, info in vnics:
                LOG.info(self.NET_USAGE_MESSAGE, instance_name,
                         vnic.name, info.rx_bytes, info.tx_bytes)
                yield self._get_counter(instance, vnic, info)
        except Exception as err:
            LOG.warning('Ignoring instance %s: %s',
                        instance_name, err)
            LOG.exception(err)


class IncomingBytesPollster(_Base):

    @staticmethod
    def get_counter_names():
        return ['network.incoming.bytes']

    def _get_counter(self, instance, vnic, info):
        return self.make_vnic_counter(
            instance,
            name='network.incoming.bytes',
            type=counter.TYPE_CUMULATIVE,
            unit='B',
            volume=info.rx_bytes,
            vnic_data=vnic,
        )


class IncomingPacketsPollster(_Base):

    @staticmethod
    def get_counter_names():
        return ['network.incoming.packets']

    def _get_counter(self, instance, vnic, info):
        return self.make_vnic_counter(
            instance,
            name='network.incoming.packets',
            type=counter.TYPE_CUMULATIVE,
            unit='packet',
            volume=info.rx_packets,
            vnic_data=vnic,
        )


class OutgoingBytesPollster(_Base):

    @staticmethod
    def get_counter_names():
        return ['network.outgoing.bytes']

    def _get_counter(self, instance, vnic, info):
        return self.make_vnic_counter(
            instance,
            name='network.outgoing.bytes',
            type=counter.TYPE_CUMULATIVE,
            unit='B',
            volume=info.tx_bytes,
            vnic_data=vnic,
        )


class OutgoingPacketsPollster(_Base):

    @staticmethod
    def get_counter_names():
        return ['network.outgoing.packets']

    def _get_counter(self, instance, vnic, info):
        return self.make_vnic_counter(
            instance,
            name='network.outgoing.packets',
            type=counter.TYPE_CUMULATIVE,
            unit='packet',
            volume=info.tx_packets,
            vnic_data=vnic,
        )
