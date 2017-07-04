# Copyright (C) 2014 eNovance SAS <licensing@enovance.com>
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

import re

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
      (default "http")
    * virtual_network
      Specify the virtual network.
      (default None)
    * fqdn_uuid:
      Specify the VM fqdn UUID.
      (default "*")
    * resource:
      The resource on which the counters are retrieved.
      (default "if_stats_list")

      * fip_stats_list:
        Traffic on floating ips
      * if_stats_list:
        Traffic on VM interfaces

    e.g.::

      opencontrail://localhost:8081/?resource=fip_stats_list&
      virtual_network=default-domain:openstack:public
    """
    def _prepare_cache(self, endpoint, params, cache):

        if 'network.statistics.opencontrail' in cache:
            return cache['network.statistics.opencontrail']

        data = {
            'o_client': client.Client(self.conf, endpoint),
            'n_client': neutron_client.Client(self.conf)
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
        ports_map = dict((port['id'], port) for port in ports)

        resource = params.get('resource', ['if_stats_list'])[0]
        fqdn_uuid = params.get('fqdn_uuid', ['*'])[0]
        virtual_network = params.get('virtual_network', [None])[0]

        statistics = data['o_client'].networks.get_vm_statistics(fqdn_uuid)
        if not statistics:
            return

        for value in statistics['value']:
            for sample in iter(extractor, value, ports_map,
                               resource, virtual_network):
                if sample is not None:
                    yield sample + (None, )

    def _get_iter(self, meter_name):
        if meter_name.startswith('switch.port'):
            return self._iter_port

    def _get_extractor(self, meter_name):
        method_name = '_' + meter_name.replace('.', '_')
        return getattr(self, method_name, None)

    @staticmethod
    def _explode_name(fq_name):
        m = re.match(
            "(?P<domain>[^:]+):(?P<project>.+):(?P<port_id>[^:]+)",
            fq_name)
        if not m:
            return
        return m.group('domain'), m.group('project'), m.group('port_id')

    @staticmethod
    def _get_resource_meta(ports_map, stat, resource, network):
        if resource == 'fip_stats_list':
            if network and (network != stat['virtual_network']):
                return
            name = stat['iface_name']
        else:
            name = stat['name']

        domain, project, port_id = OpencontrailDriver._explode_name(name)
        port = ports_map.get(port_id)

        tenant_id = None
        network_id = None
        device_owner_id = None

        if port:
            tenant_id = port['tenant_id']
            network_id = port['network_id']
            device_owner_id = port['device_id']

        resource_meta = {'device_owner_id': device_owner_id,
                         'network_id': network_id,
                         'project_id': tenant_id,
                         'project': project,
                         'resource': resource,
                         'domain': domain}

        return port_id, resource_meta

    @staticmethod
    def _iter_port(extractor, value, ports_map, resource,
                   virtual_network=None):
        stats = value['value']['UveVirtualMachineAgent'].get(resource, [])
        for stat in stats:
            if type(stat) is list:
                for sub_stats, node in zip(*[iter(stat)] * 2):
                    for sub_stat in sub_stats:
                        result = OpencontrailDriver._get_resource_meta(
                            ports_map, sub_stat, resource, virtual_network)
                        if not result:
                            continue
                        port_id, resource_meta = result
                        yield extractor(sub_stat, port_id, resource_meta)
            else:
                result = OpencontrailDriver._get_resource_meta(
                    ports_map, stat, resource, virtual_network)
                if not result:
                    continue
                port_id, resource_meta = result
                yield extractor(stat, port_id, resource_meta)

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
