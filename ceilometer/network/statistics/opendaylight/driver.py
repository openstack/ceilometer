#
# Copyright 2013 NEC Corporation.  All rights reserved.
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

from oslo_log import log
import six
from six import moves
from six.moves.urllib import parse as urlparse

from ceilometer.network.statistics import driver
from ceilometer.network.statistics.opendaylight import client
from ceilometer import utils


LOG = log.getLogger(__name__)


def _get_properties(properties, prefix='properties'):
    resource_meta = {}
    if properties is not None:
        for k, v in six.iteritems(properties):
            value = v['value']
            key = prefix + '_' + k
            if 'name' in v:
                key += '_' + v['name']
            resource_meta[key] = value
    return resource_meta


def _get_int_sample(key, statistic, resource_id, resource_meta):
    if key not in statistic:
        return None
    return int(statistic[key]), resource_id, resource_meta


class OpenDayLightDriver(driver.Driver):
    """Driver of network info collector from OpenDaylight.

    This driver uses resources in "pipeline.yaml".
    Resource requires below conditions:

    * resource is url
    * scheme is "opendaylight"

    This driver can be configured via query parameters.
    Supported parameters:

    * scheme:
      The scheme of request url to OpenDaylight REST API endpoint.
      (default http)
    * auth:
      Auth strategy of http.
      This parameter can be set basic and digest.(default None)
    * user:
      This is username that is used by auth.(default None)
    * password:
      This is password that is used by auth.(default None)
    * container_name:
      Name of container of OpenDaylight.(default "default")
      This parameter allows multi values.

    e.g.::

      opendaylight://127.0.0.1:8080/controller/nb/v2?container_name=default&
      container_name=egg&auth=basic&user=admin&password=admin&scheme=http

    In this case, the driver send request to below URLs:

      http://127.0.0.1:8080/controller/nb/v2/statistics/default/flow
      http://127.0.0.1:8080/controller/nb/v2/statistics/egg/flow
    """
    def _prepare_cache(self, endpoint, params, cache):

        if 'network.statistics.opendaylight' in cache:
            return cache['network.statistics.opendaylight']

        data = {}

        container_names = params.get('container_name', ['default'])

        odl_params = {}
        if 'auth' in params:
            odl_params['auth'] = params['auth'][0]
        if 'user' in params:
            odl_params['user'] = params['user'][0]
        if 'password' in params:
            odl_params['password'] = params['password'][0]
        cs = client.Client(self.conf, endpoint, odl_params)

        for container_name in container_names:
            try:
                container_data = {}

                # get flow statistics
                container_data['flow'] = cs.statistics.get_flow_statistics(
                    container_name)

                # get port statistics
                container_data['port'] = cs.statistics.get_port_statistics(
                    container_name)

                # get table statistics
                container_data['table'] = cs.statistics.get_table_statistics(
                    container_name)

                # get topology
                container_data['topology'] = cs.topology.get_topology(
                    container_name)

                # get switch information
                container_data['switch'] = cs.switch_manager.get_nodes(
                    container_name)

                # get and optimize user links
                # e.g.
                # before:
                #   "OF|2@OF|00:00:00:00:00:00:00:02"
                # after:
                #   {
                #       'port': {
                #           'type': 'OF',
                #           'id': '2'},
                #       'node': {
                #           'type': 'OF',
                #           'id': '00:00:00:00:00:00:00:02'
                #       }
                #   }
                user_links_raw = cs.topology.get_user_links(container_name)
                user_links = []
                container_data['user_links'] = user_links
                for user_link_row in user_links_raw['userLinks']:
                    user_link = {}
                    for k, v in six.iteritems(user_link_row):
                        if (k == "dstNodeConnector" or
                                k == "srcNodeConnector"):
                            port_raw, node_raw = v.split('@')
                            port = {}
                            port['type'], port['id'] = port_raw.split('|')
                            node = {}
                            node['type'], node['id'] = node_raw.split('|')
                            v = {'port': port, 'node': node}
                        user_link[k] = v
                    user_links.append(user_link)

                # get link status to hosts
                container_data['active_hosts'] = (
                    cs.host_tracker.get_active_hosts(container_name))
                container_data['inactive_hosts'] = (
                    cs.host_tracker.get_inactive_hosts(container_name))
                data[container_name] = container_data
            except Exception:
                LOG.exception('Request failed to connect to OpenDaylight'
                              ' with NorthBound REST API')

        cache['network.statistics.opendaylight'] = data

        return data

    def get_sample_data(self, meter_name, parse_url, params, cache):

        extractor = self._get_extractor(meter_name)
        if extractor is None:
            # The way to getting meter is not implemented in this driver or
            # OpenDaylight REST API has not api to getting meter.
            return None

        iter = self._get_iter(meter_name)
        if iter is None:
            # The way to getting meter is not implemented in this driver or
            # OpenDaylight REST API has not api to getting meter.
            return None

        parts = urlparse.ParseResult(params.get('scheme', ['http'])[0],
                                     parse_url.netloc,
                                     parse_url.path,
                                     None,
                                     None,
                                     None)
        endpoint = urlparse.urlunparse(parts)

        data = self._prepare_cache(endpoint, params, cache)

        samples = []
        for name, value in six.iteritems(data):
            for sample in iter(extractor, value):
                if sample is not None:
                    # set controller name and container name
                    # to resource_metadata
                    sample[2]['controller'] = 'OpenDaylight'
                    sample[2]['container'] = name

                    samples.append(sample + (None, ))

        return samples

    def _get_iter(self, meter_name):
        if meter_name == 'switch':
            return self._iter_switch
        elif meter_name.startswith('switch.flow'):
            return self._iter_flow
        elif meter_name.startswith('switch.table'):
            return self._iter_table
        elif meter_name.startswith('switch.port'):
            return self._iter_port

    def _get_extractor(self, meter_name):
        method_name = '_' + meter_name.replace('.', '_')
        return getattr(self, method_name, None)

    @staticmethod
    def _iter_switch(extractor, data):
        for switch in data['switch']['nodeProperties']:
            yield extractor(switch, switch['node']['id'], {})

    @staticmethod
    def _switch(statistic, resource_id, resource_meta):

        resource_meta.update(_get_properties(statistic.get('properties')))

        return 1, resource_id, resource_meta

    @staticmethod
    def _iter_port(extractor, data):
        for port_statistic in data['port']['portStatistics']:
            for statistic in port_statistic['portStatistic']:
                resource_meta = {'port': statistic['nodeConnector']['id']}
                yield extractor(statistic, port_statistic['node']['id'],
                                resource_meta, data)

    @staticmethod
    def _switch_port(statistic, resource_id, resource_meta, data):
        my_node_id = resource_id
        my_port_id = statistic['nodeConnector']['id']

        # link status from topology
        edge_properties = data['topology']['edgeProperties']
        for edge_property in edge_properties:
            edge = edge_property['edge']

            if (edge['headNodeConnector']['node']['id'] == my_node_id and
                    edge['headNodeConnector']['id'] == my_port_id):
                target_node = edge['tailNodeConnector']
            elif (edge['tailNodeConnector']['node']['id'] == my_node_id and
                    edge['tailNodeConnector']['id'] == my_port_id):
                target_node = edge['headNodeConnector']
            else:
                continue

            resource_meta['topology_node_id'] = target_node['node']['id']
            resource_meta['topology_node_port'] = target_node['id']

            resource_meta.update(_get_properties(
                edge_property.get('properties'),
                prefix='topology'))

            break

        # link status from user links
        for user_link in data['user_links']:
            if (user_link['dstNodeConnector']['node']['id'] == my_node_id and
                    user_link['dstNodeConnector']['port']['id'] == my_port_id):
                target_node = user_link['srcNodeConnector']
            elif (user_link['srcNodeConnector']['node']['id'] == my_node_id and
                    user_link['srcNodeConnector']['port']['id'] == my_port_id):
                target_node = user_link['dstNodeConnector']
            else:
                continue

            resource_meta['user_link_node_id'] = target_node['node']['id']
            resource_meta['user_link_node_port'] = target_node['port']['id']
            resource_meta['user_link_status'] = user_link['status']
            resource_meta['user_link_name'] = user_link['name']

            break

        # link status to hosts
        for hosts, status in moves.zip(
                [data['active_hosts'], data['inactive_hosts']],
                ['active', 'inactive']):
            for host_config in hosts['hostConfig']:
                if (host_config['nodeId'] != my_node_id or
                        host_config['nodeConnectorId'] != my_port_id):
                    continue

                resource_meta['host_status'] = status
                for key in ['dataLayerAddress', 'vlan', 'staticHost',
                            'networkAddress']:
                    if key in host_config:
                        resource_meta['host_' + key] = host_config[key]

                break

        return 1, resource_id, resource_meta

    @staticmethod
    def _switch_port_receive_packets(statistic, resource_id,
                                     resource_meta, data):
        return _get_int_sample('receivePackets', statistic, resource_id,
                               resource_meta)

    @staticmethod
    def _switch_port_transmit_packets(statistic, resource_id,
                                      resource_meta, data):
        return _get_int_sample('transmitPackets', statistic, resource_id,
                               resource_meta)

    @staticmethod
    def _switch_port_receive_bytes(statistic, resource_id,
                                   resource_meta, data):
        return _get_int_sample('receiveBytes', statistic, resource_id,
                               resource_meta)

    @staticmethod
    def _switch_port_transmit_bytes(statistic, resource_id,
                                    resource_meta, data):
        return _get_int_sample('transmitBytes', statistic, resource_id,
                               resource_meta)

    @staticmethod
    def _switch_port_receive_drops(statistic, resource_id,
                                   resource_meta, data):
        return _get_int_sample('receiveDrops', statistic, resource_id,
                               resource_meta)

    @staticmethod
    def _switch_port_transmit_drops(statistic, resource_id,
                                    resource_meta, data):
        return _get_int_sample('transmitDrops', statistic, resource_id,
                               resource_meta)

    @staticmethod
    def _switch_port_receive_errors(statistic, resource_id,
                                    resource_meta, data):
        return _get_int_sample('receiveErrors', statistic, resource_id,
                               resource_meta)

    @staticmethod
    def _switch_port_transmit_errors(statistic, resource_id,
                                     resource_meta, data):
        return _get_int_sample('transmitErrors', statistic, resource_id,
                               resource_meta)

    @staticmethod
    def _switch_port_receive_frame_error(statistic, resource_id,
                                         resource_meta, data):
        return _get_int_sample('receiveFrameError', statistic, resource_id,
                               resource_meta)

    @staticmethod
    def _switch_port_receive_overrun_error(statistic, resource_id,
                                           resource_meta, data):
        return _get_int_sample('receiveOverRunError', statistic, resource_id,
                               resource_meta)

    @staticmethod
    def _switch_port_receive_crc_error(statistic, resource_id,
                                       resource_meta, data):
        return _get_int_sample('receiveCrcError', statistic, resource_id,
                               resource_meta)

    @staticmethod
    def _switch_port_collision_count(statistic, resource_id,
                                     resource_meta, data):
        return _get_int_sample('collisionCount', statistic, resource_id,
                               resource_meta)

    @staticmethod
    def _iter_table(extractor, data):
        for table_statistic in data['table']['tableStatistics']:
            for statistic in table_statistic['tableStatistic']:
                resource_meta = {'table_id': statistic['nodeTable']['id']}
                yield extractor(statistic,
                                table_statistic['node']['id'],
                                resource_meta)

    @staticmethod
    def _switch_table(statistic, resource_id, resource_meta):
        return 1, resource_id, resource_meta

    @staticmethod
    def _switch_table_active_entries(statistic, resource_id,
                                     resource_meta):
        return _get_int_sample('activeCount', statistic, resource_id,
                               resource_meta)

    @staticmethod
    def _switch_table_lookup_packets(statistic, resource_id,
                                     resource_meta):
        return _get_int_sample('lookupCount', statistic, resource_id,
                               resource_meta)

    @staticmethod
    def _switch_table_matched_packets(statistic, resource_id,
                                      resource_meta):
        return _get_int_sample('matchedCount', statistic, resource_id,
                               resource_meta)

    @staticmethod
    def _iter_flow(extractor, data):
        for flow_statistic in data['flow']['flowStatistics']:
            for statistic in flow_statistic['flowStatistic']:
                resource_meta = {'flow_id': statistic['flow']['id'],
                                 'table_id': statistic['tableId']}
                for key, value in utils.dict_to_keyval(statistic['flow'],
                                                       'flow'):
                    resource_meta[key.replace('.', '_')] = value
                yield extractor(statistic,
                                flow_statistic['node']['id'],
                                resource_meta)

    @staticmethod
    def _switch_flow(statistic, resource_id, resource_meta):
        return 1, resource_id, resource_meta

    @staticmethod
    def _switch_flow_duration_seconds(statistic, resource_id,
                                      resource_meta):
        return _get_int_sample('durationSeconds', statistic, resource_id,
                               resource_meta)

    @staticmethod
    def _switch_flow_duration_nanoseconds(statistic, resource_id,
                                          resource_meta):
        return _get_int_sample('durationNanoseconds', statistic, resource_id,
                               resource_meta)

    @staticmethod
    def _switch_flow_packets(statistic, resource_id, resource_meta):
        return _get_int_sample('packetCount', statistic, resource_id,
                               resource_meta)

    @staticmethod
    def _switch_flow_bytes(statistic, resource_id, resource_meta):
        return _get_int_sample('byteCount', statistic, resource_id,
                               resource_meta)
