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

from ceilometer.compute import pollsters
from ceilometer.compute.pollsters import util
from ceilometer import sample


class NetworkPollster(pollsters.GenericComputePollster):
    inspector_method = "inspect_vnics"

    @staticmethod
    def get_additional_metadata(instance, stats):
        additional_stats = {k: getattr(stats, k)
                            for k in ["name", "mac", "fref", "parameters"]}
        if stats.fref is not None:
            additional_stats['vnic_name'] = stats.fref
        else:
            additional_stats['vnic_name'] = stats.name
        return additional_stats

    @staticmethod
    def get_resource_id(instance, stats):
        if stats.fref is not None:
            return stats.fref
        else:
            instance_name = util.instance_name(instance)
            return "%s-%s-%s" % (instance_name, instance.id, stats.name)


class IncomingBytesPollster(NetworkPollster):
    sample_name = 'network.incoming.bytes'
    sample_type = sample.TYPE_CUMULATIVE
    sample_unit = 'B'
    sample_stats_key = 'rx_bytes'


class IncomingPacketsPollster(NetworkPollster):
    sample_name = 'network.incoming.packets'
    sample_type = sample.TYPE_CUMULATIVE
    sample_unit = 'packet'
    sample_stats_key = 'rx_packets'


class OutgoingBytesPollster(NetworkPollster):
    sample_name = 'network.outgoing.bytes'
    sample_type = sample.TYPE_CUMULATIVE
    sample_unit = 'B'
    sample_stats_key = 'tx_bytes'


class OutgoingPacketsPollster(NetworkPollster):
    sample_name = 'network.outgoing.packets'
    sample_type = sample.TYPE_CUMULATIVE
    sample_unit = 'packet'
    sample_stats_key = 'tx_packets'


class IncomingBytesRatePollster(NetworkPollster):
    inspector_method = "inspect_vnic_rates"
    sample_name = 'network.incoming.bytes.rate'
    sample_unit = 'B/s'
    sample_stats_key = 'rx_bytes_rate'


class OutgoingBytesRatePollster(NetworkPollster):
    inspector_method = "inspect_vnic_rates"
    sample_name = 'network.outgoing.bytes.rate'
    sample_unit = 'B/s'
    sample_stats_key = 'tx_bytes_rate'


class IncomingDropPollster(NetworkPollster):
    sample_name = 'network.incoming.packets.drop'
    sample_type = sample.TYPE_CUMULATIVE
    sample_unit = 'packet'
    sample_stats_key = 'rx_drop'


class OutgoingDropPollster(NetworkPollster):
    sample_name = 'network.outgoing.packets.drop'
    sample_type = sample.TYPE_CUMULATIVE
    sample_unit = 'packet'
    sample_stats_key = 'tx_drop'


class IncomingErrorsPollster(NetworkPollster):
    sample_name = 'network.incoming.packets.error'
    sample_type = sample.TYPE_CUMULATIVE
    sample_unit = 'packet'
    sample_stats_key = 'rx_errors'


class OutgoingErrorsPollster(NetworkPollster):
    sample_name = 'network.outgoing.packets.error'
    sample_type = sample.TYPE_CUMULATIVE
    sample_unit = 'packet'
    sample_stats_key = 'tx_errors'
