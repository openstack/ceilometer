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

from ceilometer.compute import plugin
from ceilometer.compute.pollsters import util
from ceilometer.compute.virt import inspector as virt_inspector
from ceilometer.openstack.common.gettextutils import _  # noqa
from ceilometer.openstack.common import log
from ceilometer.openstack.common import timeutils
from ceilometer import sample

LOG = log.getLogger(__name__)


class _Base(plugin.ComputePollster):

    NET_USAGE_MESSAGE = ' '.join(["NETWORK USAGE:", "%s %s:", "read-bytes=%d",
                                  "write-bytes=%d"])

    @staticmethod
    def make_vnic_sample(instance, name, type, unit, volume, vnic_data):
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

        return sample.Sample(
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

    def get_samples(self, manager, cache, instance):
        instance_name = util.instance_name(instance)
        LOG.info(_('checking instance %s'), instance.id)
        try:
            vnics = self._get_vnics_for_instance(
                cache,
                manager.inspector,
                instance_name,
            )
            for vnic, info in vnics:
                LOG.info(self.NET_USAGE_MESSAGE, instance_name,
                         vnic.name, info.rx_bytes, info.tx_bytes)
                yield self._get_sample(instance, vnic, info)
        except virt_inspector.InstanceNotFoundException as err:
            # Instance was deleted while getting samples. Ignore it.
            LOG.debug(_('Exception while getting samples %s'), err)
        except Exception as err:
            LOG.warning(_('Ignoring instance %(name)s: %(error)s') % (
                        {'name': instance_name, 'error': err}))
            LOG.exception(err)


class IncomingBytesPollster(_Base):

    def _get_sample(self, instance, vnic, info):
        return self.make_vnic_sample(
            instance,
            name='network.incoming.bytes',
            type=sample.TYPE_CUMULATIVE,
            unit='B',
            volume=info.rx_bytes,
            vnic_data=vnic,
        )


class IncomingPacketsPollster(_Base):

    def _get_sample(self, instance, vnic, info):
        return self.make_vnic_sample(
            instance,
            name='network.incoming.packets',
            type=sample.TYPE_CUMULATIVE,
            unit='packet',
            volume=info.rx_packets,
            vnic_data=vnic,
        )


class OutgoingBytesPollster(_Base):

    def _get_sample(self, instance, vnic, info):
        return self.make_vnic_sample(
            instance,
            name='network.outgoing.bytes',
            type=sample.TYPE_CUMULATIVE,
            unit='B',
            volume=info.tx_bytes,
            vnic_data=vnic,
        )


class OutgoingPacketsPollster(_Base):

    def _get_sample(self, instance, vnic, info):
        return self.make_vnic_sample(
            instance,
            name='network.outgoing.packets',
            type=sample.TYPE_CUMULATIVE,
            unit='packet',
            volume=info.tx_packets,
            vnic_data=vnic,
        )
