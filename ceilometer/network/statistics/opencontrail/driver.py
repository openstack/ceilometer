# Copyright (C) 2014 eNovance SAS <licensing@enovance.com>
#
# Author: Sylvain Afchain <sylvain.afchain@enovance.com>
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
from oslo.utils import timeutils
from six.moves.urllib import parse as urlparse

from ceilometer.network.statistics import driver
from ceilometer.network.statistics.opencontrail import client
from ceilometer import neutron_client


class OpencontrailDriver(driver.Driver):
    """Driver of network analytics of Opencontrail.

    This driver uses resources in "pipeline.yaml".
    Resource requires below conditions:

    * resource is url
    * scheme is "opencontrail"

    This driver can be configured via query parameters.
    Supported parameters:

    * scheme:
      The scheme of request url to Opencontrail Analytics endpoint.
      (default http)
    * username:
      This is username used by Opencontrail Analytics.(default None)
    * password:
      This is password used by Opencontrail Analytics.(default None)
    * domain:
      This is domain used by Opencontrail Analytics.(default None)
    * verify_ssl:
      Specify if the certificate will be checked for https request.
      (default false)

    e.g.::

      opencontrail://localhost:8143/?username=admin&password=admin&
      scheme=https&domain=&verify_ssl=true
    """
    @staticmethod
    def _prepare_cache(endpoint, params, cache):

        if 'network.statistics.opencontrail' in cache:
            return cache['network.statistics.opencontrail']

        data = {
            'o_client': client.Client(endpoint,
                                      params['username'],
                                      params['password'],
                                      params.get('domain'),
                                      params.get('verify_ssl') == 'true'),
            'n_client': neutron_client.Client()
        }

        cache['network.statistics.opencontrail'] = data

        return data

    def get_sample_data(self, meter_name, parse_url, params, cache):

        parts = urlparse.ParseResult(params.get('scheme', ['http'])[0],
                                     parse_url.netloc,
                                     parse_url.path,
                                     None,
                                     None,
                                     None)
        endpoint = urlparse.urlunparse(parts)

        iter = self._get_iter(meter_name)
        if iter is None:
            # The extractor for this meter is not implemented or the API
            # doesn't have method to get this meter.
            return

        extractor = self._get_extractor(meter_name)
        if extractor is None:
            # The extractor for this meter is not implemented or the API
            # doesn't have method to get this meter.
            return

        data = self._prepare_cache(endpoint, params, cache)

        ports = data['n_client'].port_get_all()
        ports_map = dict((port['id'], port['tenant_id']) for port in ports)

        networks = data['n_client'].network_get_all()

        for network in networks:
            net_id = network['id']

            timestamp = timeutils.utcnow().isoformat()
            statistics = data['o_client'].networks.get_port_statistics(net_id)
            if not statistics:
                continue

            for value in statistics['value']:
                for sample in iter(extractor, value, ports_map):
                    if sample is not None:
                        sample[2]['network_id'] = net_id
                        yield sample + (timestamp, )

    def _get_iter(self, meter_name):
        if meter_name.startswith('switch.port'):
            return self._iter_port

    def _get_extractor(self, meter_name):
        method_name = '_' + meter_name.replace('.', '_')
        return getattr(self, method_name, None)

    @staticmethod
    def _iter_port(extractor, value, ports_map):
        ifstats = value['value']['UveVirtualMachineAgent']['if_stats_list']
        for ifstat in ifstats:
            name = ifstat['name']
            device_owner_id, port_id = name.split(':')

            tenant_id = ports_map.get(port_id)

            resource_meta = {'device_owner_id': device_owner_id,
                             'tenant_id': tenant_id}
            yield extractor(ifstat, port_id, resource_meta)

    @staticmethod
    def _switch_port_receive_packets(statistic, resource_id, resource_meta):
        return int(statistic['in_pkts']), resource_id, resource_meta

    @staticmethod
    def _switch_port_transmit_packets(statistic, resource_id, resource_meta):
        return int(statistic['out_pkts']), resource_id, resource_meta

    @staticmethod
    def _switch_port_receive_bytes(statistic, resource_id, resource_meta):
        return int(statistic['in_bytes']), resource_id, resource_meta

    @staticmethod
    def _switch_port_transmit_bytes(statistic, resource_id, resource_meta):
        return int(statistic['out_bytes']), resource_id, resource_meta
