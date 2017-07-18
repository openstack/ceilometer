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

import copy

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


class _Base(pollsters.BaseComputePollster):

    NET_USAGE_MESSAGE = ' '.join(["NETWORK USAGE:", "%s %s:", "read-bytes=%d",
                                  "write-bytes=%d"])

    def make_vnic_sample(self, instance, name, type, unit, volume, vnic_data,
                         monotonic_time):
        metadata = copy.copy(vnic_data)
        additional_metadata = dict(zip(metadata._fields, metadata))
        if vnic_data.fref is not None:
            rid = vnic_data.fref
            additional_metadata['vnic_name'] = vnic_data.fref
        else:
            instance_name = util.instance_name(instance)
            rid = "%s-%s-%s" % (instance_name, instance.id, vnic_data.name)
            additional_metadata['vnic_name'] = vnic_data.name

        return util.make_sample_from_instance(
            conf=self.conf,
            instance=instance,
            name=name,
            type=type,
            unit=unit,
            volume=volume,
            resource_id=rid,
            additional_metadata=additional_metadata,
            monotonic_time=monotonic_time,
        )

    CACHE_KEY_VNIC = 'vnics'

    def _get_vnic_info(self, inspector, instance):
        return inspector.inspect_vnics(instance)

    @staticmethod
    def _get_rx_info(info):
        return info.rx_bytes

    @staticmethod
    def _get_tx_info(info):
        return info.tx_bytes

    def _get_vnics_for_instance(self, cache, inspector, instance):
        i_cache = cache.setdefault(self.CACHE_KEY_VNIC, {})
        if instance.id not in i_cache:
            data = list(self._get_vnic_info(inspector, instance))
            polled_time = monotonic.monotonic()
            i_cache[instance.id] = [(vnic, info, polled_time)
                                    for vnic, info in data]
        return i_cache[instance.id]

    def get_samples(self, manager, cache, resources):
        self._inspection_duration = self._record_poll_time()
        for instance in resources:
            instance_name = util.instance_name(instance)
            LOG.debug('checking net info for instance %s', instance.id)
            try:
                vnics = self._get_vnics_for_instance(
                    cache,
                    self.inspector,
                    instance,
                )
                for vnic, info, polled_time in vnics:
                    LOG.debug(self.NET_USAGE_MESSAGE, instance_name,
                              vnic.name, self._get_rx_info(info),
                              self._get_tx_info(info))
                    yield self._get_sample(instance, vnic, info, polled_time)
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
                          '%(pollster)s',
                          {'inspector': self.inspector.__class__.__name__,
                           'pollster': self.__class__.__name__})
                raise plugin_base.PollsterPermanentError(resources)
            except Exception as err:
                LOG.exception(_('Ignoring instance %(name)s: %(error)s'),
                              {'name': instance_name, 'error': err})


class _RateBase(_Base):

    NET_USAGE_MESSAGE = ' '.join(["NETWORK RATE:", "%s %s:",
                                  "read-bytes-rate=%d",
                                  "write-bytes-rate=%d"])

    CACHE_KEY_VNIC = 'vnic-rates'

    def _get_vnic_info(self, inspector, instance):
        return inspector.inspect_vnic_rates(instance,
                                            self._inspection_duration)

    @staticmethod
    def _get_rx_info(info):
        return info.rx_bytes_rate

    @staticmethod
    def _get_tx_info(info):
        return info.tx_bytes_rate


class _PacketsBase(_Base):

    NET_USAGE_MESSAGE = ' '.join(["NETWORK USAGE:", "%s %s:",
                                  "read-packets=%d",
                                  "write-packets=%d"])

    @staticmethod
    def _get_rx_info(info):
        return info.rx_packets

    @staticmethod
    def _get_tx_info(info):
        return info.tx_packets


class _DropBase(_Base):

    NET_USAGE_MESSAGE = ' '.join(["NETWORK PACKET DROPS:", "%s %s:",
                                  "rx-drop=%d", "tx-drop=%d"])

    @staticmethod
    def _get_rx_info(info):
        return info.rx_drop

    @staticmethod
    def _get_tx_info(info):
        return info.tx_drop


class _ErrorsBase(_Base):

    NET_USAGE_MESSAGE = ' '.join(["NETWORK PACKET ERRORS:", "%s %s:",
                                  "rx-errors=%d", "tx-errors=%d"])

    @staticmethod
    def _get_rx_info(info):
        return info.rx_errors

    @staticmethod
    def _get_tx_info(info):
        return info.tx_errors


class IncomingBytesPollster(_Base):

    def _get_sample(self, instance, vnic, info, polled_time):
        return self.make_vnic_sample(
            instance,
            name='network.incoming.bytes',
            type=sample.TYPE_CUMULATIVE,
            unit='B',
            volume=info.rx_bytes,
            vnic_data=vnic,
            monotonic_time=polled_time,
        )


class IncomingPacketsPollster(_PacketsBase):

    def _get_sample(self, instance, vnic, info, polled_time):
        return self.make_vnic_sample(
            instance,
            name='network.incoming.packets',
            type=sample.TYPE_CUMULATIVE,
            unit='packet',
            volume=info.rx_packets,
            vnic_data=vnic,
            monotonic_time=polled_time,
        )


class OutgoingBytesPollster(_Base):

    def _get_sample(self, instance, vnic, info, polled_time):
        return self.make_vnic_sample(
            instance,
            name='network.outgoing.bytes',
            type=sample.TYPE_CUMULATIVE,
            unit='B',
            volume=info.tx_bytes,
            vnic_data=vnic,
            monotonic_time=polled_time,
        )


class OutgoingPacketsPollster(_PacketsBase):

    def _get_sample(self, instance, vnic, info, polled_time):
        return self.make_vnic_sample(
            instance,
            name='network.outgoing.packets',
            type=sample.TYPE_CUMULATIVE,
            unit='packet',
            volume=info.tx_packets,
            vnic_data=vnic,
            monotonic_time=polled_time,
        )


class IncomingBytesRatePollster(_RateBase):

    def _get_sample(self, instance, vnic, info, polled_time):
        return self.make_vnic_sample(
            instance,
            name='network.incoming.bytes.rate',
            type=sample.TYPE_GAUGE,
            unit='B/s',
            volume=info.rx_bytes_rate,
            vnic_data=vnic,
            monotonic_time=polled_time,
        )


class OutgoingBytesRatePollster(_RateBase):

    def _get_sample(self, instance, vnic, info, polled_time):
        return self.make_vnic_sample(
            instance,
            name='network.outgoing.bytes.rate',
            type=sample.TYPE_GAUGE,
            unit='B/s',
            volume=info.tx_bytes_rate,
            vnic_data=vnic,
            monotonic_time=polled_time,
        )


class IncomingDropPollster(_DropBase):

    def _get_sample(self, instance, vnic, info, polled_time):
        return self.make_vnic_sample(
            instance,
            name='network.incoming.packets.drop',
            type=sample.TYPE_CUMULATIVE,
            unit='packet',
            volume=info.rx_drop,
            vnic_data=vnic,
            monotonic_time=polled_time,
        )


class OutgoingDropPollster(_DropBase):

    def _get_sample(self, instance, vnic, info, polled_time):
        return self.make_vnic_sample(
            instance,
            name='network.outgoing.packets.drop',
            type=sample.TYPE_CUMULATIVE,
            unit='packet',
            volume=info.tx_drop,
            vnic_data=vnic,
            monotonic_time=polled_time,
        )


class IncomingErrorsPollster(_ErrorsBase):

    def _get_sample(self, instance, vnic, info, polled_time):
        return self.make_vnic_sample(
            instance,
            name='network.incoming.packets.error',
            type=sample.TYPE_CUMULATIVE,
            unit='packet',
            volume=info.rx_errors,
            vnic_data=vnic,
            monotonic_time=polled_time,
        )


class OutgoingErrorsPollster(_ErrorsBase):

    def _get_sample(self, instance, vnic, info, polled_time):
        return self.make_vnic_sample(
            instance,
            name='network.outgoing.packets.error',
            type=sample.TYPE_CUMULATIVE,
            unit='packet',
            volume=info.tx_errors,
            vnic_data=vnic,
            monotonic_time=polled_time,
        )
