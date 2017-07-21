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
import abc

import mock
from oslotest import base
import six
from six.moves.urllib import parse as url_parse

from ceilometer.network.statistics.opendaylight import driver
from ceilometer import service


@six.add_metaclass(abc.ABCMeta)
class _Base(base.BaseTestCase):

    @abc.abstractproperty
    def flow_data(self):
        pass

    @abc.abstractproperty
    def port_data(self):
        pass

    @abc.abstractproperty
    def table_data(self):
        pass

    @abc.abstractproperty
    def topology_data(self):
        pass

    @abc.abstractproperty
    def switch_data(self):
        pass

    @abc.abstractproperty
    def user_links_data(self):
        pass

    @abc.abstractproperty
    def active_hosts_data(self):
        pass

    @abc.abstractproperty
    def inactive_hosts_data(self):
        pass

    fake_odl_url = url_parse.ParseResult('opendaylight',
                                         'localhost:8080',
                                         'controller/nb/v2',
                                         None,
                                         None,
                                         None)

    fake_params = url_parse.parse_qs('user=admin&password=admin&scheme=http&'
                                     'container_name=default&auth=basic')

    fake_params_multi_container = (
        url_parse.parse_qs('user=admin&password=admin&scheme=http&'
                           'container_name=first&container_name=second&'
                           'auth=basic'))

    def setUp(self):
        super(_Base, self).setUp()
        self.addCleanup(mock.patch.stopall)
        conf = service.prepare_service([], [])
        self.driver = driver.OpenDayLightDriver(conf)

        self.get_flow_statistics = mock.patch(
            'ceilometer.network.statistics.opendaylight.client.'
            'StatisticsAPIClient.get_flow_statistics',
            return_value=self.flow_data).start()

        mock.patch('ceilometer.network.statistics.opendaylight.client.'
                   'StatisticsAPIClient.get_table_statistics',
                   return_value=self.table_data).start()

        mock.patch('ceilometer.network.statistics.opendaylight.client.'
                   'StatisticsAPIClient.get_port_statistics',
                   return_value=self.port_data).start()

        mock.patch('ceilometer.network.statistics.opendaylight.client.'
                   'TopologyAPIClient.get_topology',
                   return_value=self.topology_data).start()

        mock.patch('ceilometer.network.statistics.opendaylight.client.'
                   'TopologyAPIClient.get_user_links',
                   return_value=self.user_links_data).start()

        mock.patch('ceilometer.network.statistics.opendaylight.client.'
                   'SwitchManagerAPIClient.get_nodes',
                   return_value=self.switch_data).start()

        mock.patch('ceilometer.network.statistics.opendaylight.client.'
                   'HostTrackerAPIClient.get_active_hosts',
                   return_value=self.active_hosts_data).start()

        mock.patch('ceilometer.network.statistics.opendaylight.client.'
                   'HostTrackerAPIClient.get_inactive_hosts',
                   return_value=self.inactive_hosts_data).start()

    def _test_for_meter(self, meter_name, expected_data):
        sample_data = self.driver.get_sample_data(meter_name,
                                                  self.fake_odl_url,
                                                  self.fake_params,
                                                  {})

        self.assertEqual(expected_data, list(sample_data))


class TestOpenDayLightDriverSpecial(_Base):

    flow_data = {"flowStatistics": []}
    port_data = {"portStatistics": []}
    table_data = {"tableStatistics": []}
    topology_data = {"edgeProperties": []}
    switch_data = {"nodeProperties": []}
    user_links_data = {"userLinks": []}
    active_hosts_data = {"hostConfig": []}
    inactive_hosts_data = {"hostConfig": []}

    def test_not_implemented_meter(self):
        sample_data = self.driver.get_sample_data('egg',
                                                  self.fake_odl_url,
                                                  self.fake_params,
                                                  {})
        self.assertIsNone(sample_data)

        sample_data = self.driver.get_sample_data('switch.table.egg',
                                                  self.fake_odl_url,
                                                  self.fake_params,
                                                  {})
        self.assertIsNone(sample_data)

    def test_cache(self):
        cache = {}
        self.driver.get_sample_data('switch',
                                    self.fake_odl_url,
                                    self.fake_params,
                                    cache)
        self.driver.get_sample_data('switch',
                                    self.fake_odl_url,
                                    self.fake_params,
                                    cache)
        self.assertEqual(1, self.get_flow_statistics.call_count)

        cache = {}
        self.driver.get_sample_data('switch',
                                    self.fake_odl_url,
                                    self.fake_params,
                                    cache)
        self.assertEqual(2, self.get_flow_statistics.call_count)

    def test_multi_container(self):
        cache = {}
        self.driver.get_sample_data('switch',
                                    self.fake_odl_url,
                                    self.fake_params_multi_container,
                                    cache)
        self.assertEqual(2, self.get_flow_statistics.call_count)

        self.assertIn('network.statistics.opendaylight', cache)

        odl_data = cache['network.statistics.opendaylight']

        self.assertIn('first', odl_data)
        self.assertIn('second', odl_data)

    def test_http_error(self):

        mock.patch('ceilometer.network.statistics.opendaylight.client.'
                   'StatisticsAPIClient.get_flow_statistics',
                   side_effect=Exception()).start()

        sample_data = self.driver.get_sample_data('switch',
                                                  self.fake_odl_url,
                                                  self.fake_params,
                                                  {})

        self.assertEqual(0, len(sample_data))

        mock.patch('ceilometer.network.statistics.opendaylight.client.'
                   'StatisticsAPIClient.get_flow_statistics',
                   side_effect=[Exception(), self.flow_data]).start()
        cache = {}
        self.driver.get_sample_data('switch',
                                    self.fake_odl_url,
                                    self.fake_params_multi_container,
                                    cache)

        self.assertIn('network.statistics.opendaylight', cache)

        odl_data = cache['network.statistics.opendaylight']

        self.assertIn('second', odl_data)


class TestOpenDayLightDriverSimple(_Base):

    flow_data = {
        "flowStatistics": [
            {
                "node": {
                    "id": "00:00:00:00:00:00:00:02",
                    "type": "OF"
                },
                "flowStatistic": [
                    {
                        "flow": {
                            "match": {
                                "matchField": [
                                    {
                                        "type": "DL_TYPE",
                                        "value": "2048"
                                    },
                                    {
                                        "mask": "255.255.255.255",
                                        "type": "NW_DST",
                                        "value": "1.1.1.1"
                                    }
                                ]
                            },
                            "actions": {
                                "@type": "output",
                                "port": {
                                    "id": "3",
                                    "node": {
                                        "id": "00:00:00:00:00:00:00:02",
                                        "type": "OF"
                                    },
                                    "type": "OF"
                                }
                            },
                            "hardTimeout": "0",
                            "id": "0",
                            "idleTimeout": "0",
                            "priority": "1"
                        },
                        "byteCount": "0",
                        "durationNanoseconds": "397000000",
                        "durationSeconds": "1828",
                        "packetCount": "0",
                        "tableId": "0"
                    },
                ]
            }
        ]
    }
    port_data = {
        "portStatistics": [
            {
                "node": {
                    "id": "00:00:00:00:00:00:00:02",
                    "type": "OF"
                },
                "portStatistic": [
                    {
                        "nodeConnector": {
                            "id": "4",
                            "node": {
                                "id": "00:00:00:00:00:00:00:02",
                                "type": "OF"
                            },
                            "type": "OF"
                        },
                        "collisionCount": "0",
                        "receiveBytes": "0",
                        "receiveCrcError": "0",
                        "receiveDrops": "0",
                        "receiveErrors": "0",
                        "receiveFrameError": "0",
                        "receiveOverRunError": "0",
                        "receivePackets": "0",
                        "transmitBytes": "0",
                        "transmitDrops": "0",
                        "transmitErrors": "0",
                        "transmitPackets": "0"
                    },
                ]
            }
        ]
    }
    table_data = {
        "tableStatistics": [
            {
                "node": {
                    "id": "00:00:00:00:00:00:00:02",
                    "type": "OF"
                },
                "tableStatistic": [
                    {
                        "activeCount": "11",
                        "lookupCount": "816",
                        "matchedCount": "220",
                        "nodeTable": {
                            "id": "0",
                            "node": {
                                "id": "00:00:00:00:00:00:00:02",
                                "type": "OF"
                            }
                        }
                    },
                ]
            }
        ]
    }
    topology_data = {"edgeProperties": []}
    switch_data = {
        "nodeProperties": [
            {
                "node": {
                    "id": "00:00:00:00:00:00:00:02",
                    "type": "OF"
                },
                "properties": {
                    "actions": {
                        "value": "4095"
                    },
                    "timeStamp": {
                        "name": "connectedSince",
                        "value": "1377291227877"
                    }
                }
            },
        ]
    }
    user_links_data = {"userLinks": []}
    active_hosts_data = {"hostConfig": []}
    inactive_hosts_data = {"hostConfig": []}

    def test_meter_switch(self):
        expected_data = [
            (1, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                "properties_actions": "4095",
                "properties_timeStamp_connectedSince": "1377291227877"
            }, None),
        ]

        self._test_for_meter('switch', expected_data)

    def test_meter_switch_port(self):
        expected_data = [
            (1, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4',
            }, None),
        ]
        self._test_for_meter('switch.port', expected_data)

    def test_meter_switch_port_receive_packets(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
        ]
        self._test_for_meter('switch.port.receive.packets', expected_data)

    def test_meter_switch_port_transmit_packets(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
        ]
        self._test_for_meter('switch.port.transmit.packets', expected_data)

    def test_meter_switch_port_receive_bytes(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
        ]
        self._test_for_meter('switch.port.receive.bytes', expected_data)

    def test_meter_switch_port_transmit_bytes(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
        ]
        self._test_for_meter('switch.port.transmit.bytes', expected_data)

    def test_meter_switch_port_receive_drops(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
        ]
        self._test_for_meter('switch.port.receive.drops', expected_data)

    def test_meter_switch_port_transmit_drops(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
        ]
        self._test_for_meter('switch.port.transmit.drops', expected_data)

    def test_meter_switch_port_receive_errors(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
        ]
        self._test_for_meter('switch.port.receive.errors', expected_data)

    def test_meter_switch_port_transmit_errors(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
        ]
        self._test_for_meter('switch.port.transmit.errors', expected_data)

    def test_meter_switch_port_receive_frame_error(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
        ]
        self._test_for_meter('switch.port.receive.frame_error', expected_data)

    def test_meter_switch_port_receive_overrun_error(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
        ]
        self._test_for_meter('switch.port.receive.overrun_error',
                             expected_data)

    def test_meter_switch_port_receive_crc_error(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
        ]
        self._test_for_meter('switch.port.receive.crc_error', expected_data)

    def test_meter_switch_port_collision_count(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
        ]
        self._test_for_meter('switch.port.collision.count', expected_data)

    def test_meter_switch_table(self):
        expected_data = [
            (1, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '0'}, None),
        ]
        self._test_for_meter('switch.table', expected_data)

    def test_meter_switch_table_active_entries(self):
        expected_data = [
            (11, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '0'}, None),
        ]
        self._test_for_meter('switch.table.active.entries', expected_data)

    def test_meter_switch_table_lookup_packets(self):
        expected_data = [
            (816, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '0'}, None),
        ]
        self._test_for_meter('switch.table.lookup.packets', expected_data)

    def test_meter_switch_table_matched_packets(self):
        expected_data = [
            (220, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '0'}, None),
        ]
        self._test_for_meter('switch.table.matched.packets', expected_data)

    def test_meter_switch_flow(self):
        expected_data = [
            (1, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '0',
                'flow_id': '0',
                "flow_match_matchField[0]_type": "DL_TYPE",
                "flow_match_matchField[0]_value": "2048",
                "flow_match_matchField[1]_mask": "255.255.255.255",
                "flow_match_matchField[1]_type": "NW_DST",
                "flow_match_matchField[1]_value": "1.1.1.1",
                "flow_actions_@type": "output",
                "flow_actions_port_id": "3",
                "flow_actions_port_node_id": "00:00:00:00:00:00:00:02",
                "flow_actions_port_node_type": "OF",
                "flow_actions_port_type": "OF",
                "flow_hardTimeout": "0",
                "flow_idleTimeout": "0",
                "flow_priority": "1"
            }, None),
        ]
        self._test_for_meter('switch.flow', expected_data)

    def test_meter_switch_flow_duration_seconds(self):
        expected_data = [
            (1828, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '0',
                'flow_id': '0',
                "flow_match_matchField[0]_type": "DL_TYPE",
                "flow_match_matchField[0]_value": "2048",
                "flow_match_matchField[1]_mask": "255.255.255.255",
                "flow_match_matchField[1]_type": "NW_DST",
                "flow_match_matchField[1]_value": "1.1.1.1",
                "flow_actions_@type": "output",
                "flow_actions_port_id": "3",
                "flow_actions_port_node_id": "00:00:00:00:00:00:00:02",
                "flow_actions_port_node_type": "OF",
                "flow_actions_port_type": "OF",
                "flow_hardTimeout": "0",
                "flow_idleTimeout": "0",
                "flow_priority": "1"}, None),
        ]
        self._test_for_meter('switch.flow.duration_seconds', expected_data)

    def test_meter_switch_flow_duration_nanoseconds(self):
        expected_data = [
            (397000000, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '0',
                'flow_id': '0',
                "flow_match_matchField[0]_type": "DL_TYPE",
                "flow_match_matchField[0]_value": "2048",
                "flow_match_matchField[1]_mask": "255.255.255.255",
                "flow_match_matchField[1]_type": "NW_DST",
                "flow_match_matchField[1]_value": "1.1.1.1",
                "flow_actions_@type": "output",
                "flow_actions_port_id": "3",
                "flow_actions_port_node_id": "00:00:00:00:00:00:00:02",
                "flow_actions_port_node_type": "OF",
                "flow_actions_port_type": "OF",
                "flow_hardTimeout": "0",
                "flow_idleTimeout": "0",
                "flow_priority": "1"}, None),
        ]
        self._test_for_meter('switch.flow.duration_nanoseconds', expected_data)

    def test_meter_switch_flow_packets(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '0',
                'flow_id': '0',
                "flow_match_matchField[0]_type": "DL_TYPE",
                "flow_match_matchField[0]_value": "2048",
                "flow_match_matchField[1]_mask": "255.255.255.255",
                "flow_match_matchField[1]_type": "NW_DST",
                "flow_match_matchField[1]_value": "1.1.1.1",
                "flow_actions_@type": "output",
                "flow_actions_port_id": "3",
                "flow_actions_port_node_id": "00:00:00:00:00:00:00:02",
                "flow_actions_port_node_type": "OF",
                "flow_actions_port_type": "OF",
                "flow_hardTimeout": "0",
                "flow_idleTimeout": "0",
                "flow_priority": "1"}, None),
        ]
        self._test_for_meter('switch.flow.packets', expected_data)

    def test_meter_switch_flow_bytes(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '0',
                'flow_id': '0',
                "flow_match_matchField[0]_type": "DL_TYPE",
                "flow_match_matchField[0]_value": "2048",
                "flow_match_matchField[1]_mask": "255.255.255.255",
                "flow_match_matchField[1]_type": "NW_DST",
                "flow_match_matchField[1]_value": "1.1.1.1",
                "flow_actions_@type": "output",
                "flow_actions_port_id": "3",
                "flow_actions_port_node_id": "00:00:00:00:00:00:00:02",
                "flow_actions_port_node_type": "OF",
                "flow_actions_port_type": "OF",
                "flow_hardTimeout": "0",
                "flow_idleTimeout": "0",
                "flow_priority": "1"}, None),
        ]
        self._test_for_meter('switch.flow.bytes', expected_data)


class TestOpenDayLightDriverComplex(_Base):

    flow_data = {
        "flowStatistics": [
            {
                "node": {
                    "id": "00:00:00:00:00:00:00:02",
                    "type": "OF"
                },
                "flowStatistic": [
                    {
                        "flow": {
                            "match": {
                                "matchField": [
                                    {
                                        "type": "DL_TYPE",
                                        "value": "2048"
                                    },
                                    {
                                        "mask": "255.255.255.255",
                                        "type": "NW_DST",
                                        "value": "1.1.1.1"
                                    }
                                ]
                            },
                            "actions": {
                                "@type": "output",
                                "port": {
                                    "id": "3",
                                    "node": {
                                        "id": "00:00:00:00:00:00:00:02",
                                        "type": "OF"
                                    },
                                    "type": "OF"
                                }
                            },
                            "hardTimeout": "0",
                            "id": "0",
                            "idleTimeout": "0",
                            "priority": "1"
                        },
                        "byteCount": "0",
                        "durationNanoseconds": "397000000",
                        "durationSeconds": "1828",
                        "packetCount": "0",
                        "tableId": "0"
                    },
                    {
                        "flow": {
                            "match": {
                                "matchField": [
                                    {
                                        "type": "DL_TYPE",
                                        "value": "2048"
                                    },
                                    {
                                        "mask": "255.255.255.255",
                                        "type": "NW_DST",
                                        "value": "1.1.1.2"
                                    }
                                ]
                            },
                            "actions": {
                                "@type": "output",
                                "port": {
                                    "id": "4",
                                    "node": {
                                        "id": "00:00:00:00:00:00:00:03",
                                        "type": "OF"
                                    },
                                    "type": "OF"
                                }
                            },
                            "hardTimeout": "0",
                            "id": "0",
                            "idleTimeout": "0",
                            "priority": "1"
                        },
                        "byteCount": "89",
                        "durationNanoseconds": "200000",
                        "durationSeconds": "5648",
                        "packetCount": "30",
                        "tableId": "1"
                    }
                ]
            }
        ]
    }
    port_data = {
        "portStatistics": [
            {
                "node": {
                    "id": "00:00:00:00:00:00:00:02",
                    "type": "OF"
                },
                "portStatistic": [
                    {
                        "nodeConnector": {
                            "id": "4",
                            "node": {
                                "id": "00:00:00:00:00:00:00:02",
                                "type": "OF"
                            },
                            "type": "OF"
                        },
                        "collisionCount": "0",
                        "receiveBytes": "0",
                        "receiveCrcError": "0",
                        "receiveDrops": "0",
                        "receiveErrors": "0",
                        "receiveFrameError": "0",
                        "receiveOverRunError": "0",
                        "receivePackets": "0",
                        "transmitBytes": "0",
                        "transmitDrops": "0",
                        "transmitErrors": "0",
                        "transmitPackets": "0"
                    },
                    {
                        "nodeConnector": {
                            "id": "3",
                            "node": {
                                "id": "00:00:00:00:00:00:00:02",
                                "type": "OF"
                            },
                            "type": "OF"
                        },
                        "collisionCount": "0",
                        "receiveBytes": "12740",
                        "receiveCrcError": "0",
                        "receiveDrops": "0",
                        "receiveErrors": "0",
                        "receiveFrameError": "0",
                        "receiveOverRunError": "0",
                        "receivePackets": "182",
                        "transmitBytes": "12110",
                        "transmitDrops": "0",
                        "transmitErrors": "0",
                        "transmitPackets": "173"
                    },
                    {
                        "nodeConnector": {
                            "id": "2",
                            "node": {
                                "id": "00:00:00:00:00:00:00:02",
                                "type": "OF"
                            },
                            "type": "OF"
                        },
                        "collisionCount": "0",
                        "receiveBytes": "12180",
                        "receiveCrcError": "0",
                        "receiveDrops": "0",
                        "receiveErrors": "0",
                        "receiveFrameError": "0",
                        "receiveOverRunError": "0",
                        "receivePackets": "174",
                        "transmitBytes": "12670",
                        "transmitDrops": "0",
                        "transmitErrors": "0",
                        "transmitPackets": "181"
                    },
                    {
                        "nodeConnector": {
                            "id": "1",
                            "node": {
                                "id": "00:00:00:00:00:00:00:02",
                                "type": "OF"
                            },
                            "type": "OF"
                        },
                        "collisionCount": "0",
                        "receiveBytes": "0",
                        "receiveCrcError": "0",
                        "receiveDrops": "0",
                        "receiveErrors": "0",
                        "receiveFrameError": "0",
                        "receiveOverRunError": "0",
                        "receivePackets": "0",
                        "transmitBytes": "0",
                        "transmitDrops": "0",
                        "transmitErrors": "0",
                        "transmitPackets": "0"
                    },
                    {
                        "nodeConnector": {
                            "id": "0",
                            "node": {
                                "id": "00:00:00:00:00:00:00:02",
                                "type": "OF"
                            },
                            "type": "OF"
                        },
                        "collisionCount": "0",
                        "receiveBytes": "0",
                        "receiveCrcError": "0",
                        "receiveDrops": "0",
                        "receiveErrors": "0",
                        "receiveFrameError": "0",
                        "receiveOverRunError": "0",
                        "receivePackets": "0",
                        "transmitBytes": "0",
                        "transmitDrops": "0",
                        "transmitErrors": "0",
                        "transmitPackets": "0"
                    }
                ]
            }
        ]
    }
    table_data = {
        "tableStatistics": [
            {
                "node": {
                    "id": "00:00:00:00:00:00:00:02",
                    "type": "OF"
                },
                "tableStatistic": [
                    {
                        "activeCount": "11",
                        "lookupCount": "816",
                        "matchedCount": "220",
                        "nodeTable": {
                            "id": "0",
                            "node": {
                                "id": "00:00:00:00:00:00:00:02",
                                "type": "OF"
                            }
                        }
                    },
                    {
                        "activeCount": "20",
                        "lookupCount": "10",
                        "matchedCount": "5",
                        "nodeTable": {
                            "id": "1",
                            "node": {
                                "id": "00:00:00:00:00:00:00:02",
                                "type": "OF"
                            }
                        }
                    }
                ]
            }
        ]
    }
    topology_data = {
        "edgeProperties": [
            {
                "edge": {
                    "headNodeConnector": {
                        "id": "2",
                        "node": {
                            "id": "00:00:00:00:00:00:00:03",
                            "type": "OF"
                        },
                        "type": "OF"
                    },
                    "tailNodeConnector": {
                        "id": "2",
                        "node": {
                            "id": "00:00:00:00:00:00:00:02",
                            "type": "OF"
                        },
                        "type": "OF"
                    }
                },
                "properties": {
                    "bandwidth": {
                        "value": 10000000000
                    },
                    "config": {
                        "value": 1
                    },
                    "name": {
                        "value": "s2-eth3"
                    },
                    "state": {
                        "value": 1
                    },
                    "timeStamp": {
                        "name": "creation",
                        "value": 1379527162648
                    }
                }
            },
            {
                "edge": {
                    "headNodeConnector": {
                        "id": "5",
                        "node": {
                            "id": "00:00:00:00:00:00:00:02",
                            "type": "OF"
                        },
                        "type": "OF"
                    },
                    "tailNodeConnector": {
                        "id": "2",
                        "node": {
                            "id": "00:00:00:00:00:00:00:04",
                            "type": "OF"
                        },
                        "type": "OF"
                    }
                },
                "properties": {
                    "timeStamp": {
                        "name": "creation",
                        "value": 1379527162648
                    }
                }
            }
        ]
    }
    switch_data = {
        "nodeProperties": [
            {
                "node": {
                    "id": "00:00:00:00:00:00:00:02",
                    "type": "OF"
                },
                "properties": {
                    "actions": {
                        "value": "4095"
                    },
                    "buffers": {
                        "value": "256"
                    },
                    "capabilities": {
                        "value": "199"
                    },
                    "description": {
                        "value": "None"
                    },
                    "macAddress": {
                        "value": "00:00:00:00:00:02"
                    },
                    "tables": {
                        "value": "-1"
                    },
                    "timeStamp": {
                        "name": "connectedSince",
                        "value": "1377291227877"
                    }
                }
            },
            {
                "node": {
                    "id": "00:00:00:00:00:00:00:03",
                    "type": "OF"
                },
                "properties": {
                    "actions": {
                        "value": "1024"
                    },
                    "buffers": {
                        "value": "512"
                    },
                    "capabilities": {
                        "value": "1000"
                    },
                    "description": {
                        "value": "Foo Bar"
                    },
                    "macAddress": {
                        "value": "00:00:00:00:00:03"
                    },
                    "tables": {
                        "value": "10"
                    },
                    "timeStamp": {
                        "name": "connectedSince",
                        "value": "1377291228000"
                    }
                }
            }
        ]
    }
    user_links_data = {
        "userLinks": [
            {
                "dstNodeConnector": "OF|5@OF|00:00:00:00:00:00:00:05",
                "name": "link1",
                "srcNodeConnector": "OF|3@OF|00:00:00:00:00:00:00:02",
                "status": "Success"
            }
        ]
    }
    active_hosts_data = {
        "hostConfig": [
            {
                "dataLayerAddress": "00:00:00:00:01:01",
                "networkAddress": "1.1.1.1",
                "nodeConnectorId": "9",
                "nodeConnectorType": "OF",
                "nodeId": "00:00:00:00:00:00:00:01",
                "nodeType": "OF",
                "staticHost": "false",
                "vlan": "0"
            },
            {
                "dataLayerAddress": "00:00:00:00:02:02",
                "networkAddress": "2.2.2.2",
                "nodeConnectorId": "1",
                "nodeConnectorType": "OF",
                "nodeId": "00:00:00:00:00:00:00:02",
                "nodeType": "OF",
                "staticHost": "true",
                "vlan": "0"
            }
        ]
    }
    inactive_hosts_data = {
        "hostConfig": [
            {
                "dataLayerAddress": "00:00:00:01:01:01",
                "networkAddress": "1.1.1.3",
                "nodeConnectorId": "8",
                "nodeConnectorType": "OF",
                "nodeId": "00:00:00:00:00:00:00:01",
                "nodeType": "OF",
                "staticHost": "false",
                "vlan": "0"
            },
            {
                "dataLayerAddress": "00:00:00:01:02:02",
                "networkAddress": "2.2.2.4",
                "nodeConnectorId": "0",
                "nodeConnectorType": "OF",
                "nodeId": "00:00:00:00:00:00:00:02",
                "nodeType": "OF",
                "staticHost": "false",
                "vlan": "1"
            }
        ]
    }

    def test_meter_switch(self):
        expected_data = [
            (1, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                "properties_actions": "4095",
                "properties_buffers": "256",
                "properties_capabilities": "199",
                "properties_description": "None",
                "properties_macAddress": "00:00:00:00:00:02",
                "properties_tables": "-1",
                "properties_timeStamp_connectedSince": "1377291227877"
            }, None),
            (1, "00:00:00:00:00:00:00:03", {
                'controller': 'OpenDaylight',
                'container': 'default',
                "properties_actions": "1024",
                "properties_buffers": "512",
                "properties_capabilities": "1000",
                "properties_description": "Foo Bar",
                "properties_macAddress": "00:00:00:00:00:03",
                "properties_tables": "10",
                "properties_timeStamp_connectedSince": "1377291228000"
            }, None),
        ]

        self._test_for_meter('switch', expected_data)

    def test_meter_switch_port(self):
        expected_data = [
            (1, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4',
            }, None),
            (1, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '3',
                'user_link_node_id': '00:00:00:00:00:00:00:05',
                'user_link_node_port': '5',
                'user_link_status': 'Success',
                'user_link_name': 'link1',
            }, None),
            (1, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '2',
                'topology_node_id': '00:00:00:00:00:00:00:03',
                'topology_node_port': '2',
                "topology_bandwidth": 10000000000,
                "topology_config": 1,
                "topology_name": "s2-eth3",
                "topology_state": 1,
                "topology_timeStamp_creation": 1379527162648
            }, None),
            (1, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '1',
                'host_status': 'active',
                'host_dataLayerAddress': '00:00:00:00:02:02',
                'host_networkAddress': '2.2.2.2',
                'host_staticHost': 'true',
                'host_vlan': '0',
            }, None),
            (1, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '0',
                'host_status': 'inactive',
                'host_dataLayerAddress': '00:00:00:01:02:02',
                'host_networkAddress': '2.2.2.4',
                'host_staticHost': 'false',
                'host_vlan': '1',
            }, None),
        ]
        self._test_for_meter('switch.port', expected_data)

    def test_meter_switch_port_receive_packets(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
            (182, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '3'}, None),
            (174, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '2'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '1'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '0'}, None),
        ]
        self._test_for_meter('switch.port.receive.packets', expected_data)

    def test_meter_switch_port_transmit_packets(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
            (173, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '3'}, None),
            (181, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '2'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '1'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '0'}, None),
        ]
        self._test_for_meter('switch.port.transmit.packets', expected_data)

    def test_meter_switch_port_receive_bytes(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
            (12740, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '3'}, None),
            (12180, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '2'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '1'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '0'}, None),
        ]
        self._test_for_meter('switch.port.receive.bytes', expected_data)

    def test_meter_switch_port_transmit_bytes(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
            (12110, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '3'}, None),
            (12670, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '2'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '1'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '0'}, None),
        ]
        self._test_for_meter('switch.port.transmit.bytes', expected_data)

    def test_meter_switch_port_receive_drops(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '3'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '2'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '1'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '0'}, None),
        ]
        self._test_for_meter('switch.port.receive.drops', expected_data)

    def test_meter_switch_port_transmit_drops(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '3'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '2'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '1'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '0'}, None),
        ]
        self._test_for_meter('switch.port.transmit.drops', expected_data)

    def test_meter_switch_port_receive_errors(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '3'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '2'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '1'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '0'}, None),
        ]
        self._test_for_meter('switch.port.receive.errors', expected_data)

    def test_meter_switch_port_transmit_errors(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '3'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '2'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '1'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '0'}, None),
        ]
        self._test_for_meter('switch.port.transmit.errors', expected_data)

    def test_meter_switch_port_receive_frame_error(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '3'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '2'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '1'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '0'}, None),
        ]
        self._test_for_meter('switch.port.receive.frame_error', expected_data)

    def test_meter_switch_port_receive_overrun_error(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '3'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '2'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '1'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '0'}, None),
        ]
        self._test_for_meter('switch.port.receive.overrun_error',
                             expected_data)

    def test_meter_switch_port_receive_crc_error(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '3'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '2'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '1'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '0'}, None),
        ]
        self._test_for_meter('switch.port.receive.crc_error', expected_data)

    def test_meter_switch_port_collision_count(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '4'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '3'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '2'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '1'}, None),
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'port': '0'}, None),
        ]
        self._test_for_meter('switch.port.collision.count', expected_data)

    def test_meter_switch_table(self):
        expected_data = [
            (1, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '0'}, None),
            (1, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '1'}, None),
        ]
        self._test_for_meter('switch.table', expected_data)

    def test_meter_switch_table_active_entries(self):
        expected_data = [
            (11, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '0'}, None),
            (20, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '1'}, None),
        ]
        self._test_for_meter('switch.table.active.entries', expected_data)

    def test_meter_switch_table_lookup_packets(self):
        expected_data = [
            (816, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '0'}, None),
            (10, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '1'}, None),
        ]
        self._test_for_meter('switch.table.lookup.packets', expected_data)

    def test_meter_switch_table_matched_packets(self):
        expected_data = [
            (220, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '0'}, None),
            (5, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '1'}, None),
        ]
        self._test_for_meter('switch.table.matched.packets', expected_data)

    def test_meter_switch_flow(self):
        expected_data = [
            (1, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '0',
                'flow_id': '0',
                "flow_match_matchField[0]_type": "DL_TYPE",
                "flow_match_matchField[0]_value": "2048",
                "flow_match_matchField[1]_mask": "255.255.255.255",
                "flow_match_matchField[1]_type": "NW_DST",
                "flow_match_matchField[1]_value": "1.1.1.1",
                "flow_actions_@type": "output",
                "flow_actions_port_id": "3",
                "flow_actions_port_node_id": "00:00:00:00:00:00:00:02",
                "flow_actions_port_node_type": "OF",
                "flow_actions_port_type": "OF",
                "flow_hardTimeout": "0",
                "flow_idleTimeout": "0",
                "flow_priority": "1"
            }, None),
            (1, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '1',
                'flow_id': '0',
                "flow_match_matchField[0]_type": "DL_TYPE",
                "flow_match_matchField[0]_value": "2048",
                "flow_match_matchField[1]_mask": "255.255.255.255",
                "flow_match_matchField[1]_type": "NW_DST",
                "flow_match_matchField[1]_value": "1.1.1.2",
                "flow_actions_@type": "output",
                "flow_actions_port_id": "4",
                "flow_actions_port_node_id": "00:00:00:00:00:00:00:03",
                "flow_actions_port_node_type": "OF",
                "flow_actions_port_type": "OF",
                "flow_hardTimeout": "0",
                "flow_idleTimeout": "0",
                "flow_priority": "1"
            }, None),
        ]
        self._test_for_meter('switch.flow', expected_data)

    def test_meter_switch_flow_duration_seconds(self):
        expected_data = [
            (1828, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '0',
                'flow_id': '0',
                "flow_match_matchField[0]_type": "DL_TYPE",
                "flow_match_matchField[0]_value": "2048",
                "flow_match_matchField[1]_mask": "255.255.255.255",
                "flow_match_matchField[1]_type": "NW_DST",
                "flow_match_matchField[1]_value": "1.1.1.1",
                "flow_actions_@type": "output",
                "flow_actions_port_id": "3",
                "flow_actions_port_node_id": "00:00:00:00:00:00:00:02",
                "flow_actions_port_node_type": "OF",
                "flow_actions_port_type": "OF",
                "flow_hardTimeout": "0",
                "flow_idleTimeout": "0",
                "flow_priority": "1"}, None),
            (5648, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '1',
                'flow_id': '0',
                "flow_match_matchField[0]_type": "DL_TYPE",
                "flow_match_matchField[0]_value": "2048",
                "flow_match_matchField[1]_mask": "255.255.255.255",
                "flow_match_matchField[1]_type": "NW_DST",
                "flow_match_matchField[1]_value": "1.1.1.2",
                "flow_actions_@type": "output",
                "flow_actions_port_id": "4",
                "flow_actions_port_node_id": "00:00:00:00:00:00:00:03",
                "flow_actions_port_node_type": "OF",
                "flow_actions_port_type": "OF",
                "flow_hardTimeout": "0",
                "flow_idleTimeout": "0",
                "flow_priority": "1"}, None),
        ]
        self._test_for_meter('switch.flow.duration_seconds', expected_data)

    def test_meter_switch_flow_duration_nanoseconds(self):
        expected_data = [
            (397000000, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '0',
                'flow_id': '0',
                "flow_match_matchField[0]_type": "DL_TYPE",
                "flow_match_matchField[0]_value": "2048",
                "flow_match_matchField[1]_mask": "255.255.255.255",
                "flow_match_matchField[1]_type": "NW_DST",
                "flow_match_matchField[1]_value": "1.1.1.1",
                "flow_actions_@type": "output",
                "flow_actions_port_id": "3",
                "flow_actions_port_node_id": "00:00:00:00:00:00:00:02",
                "flow_actions_port_node_type": "OF",
                "flow_actions_port_type": "OF",
                "flow_hardTimeout": "0",
                "flow_idleTimeout": "0",
                "flow_priority": "1"}, None),
            (200000, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '1',
                'flow_id': '0',
                "flow_match_matchField[0]_type": "DL_TYPE",
                "flow_match_matchField[0]_value": "2048",
                "flow_match_matchField[1]_mask": "255.255.255.255",
                "flow_match_matchField[1]_type": "NW_DST",
                "flow_match_matchField[1]_value": "1.1.1.2",
                "flow_actions_@type": "output",
                "flow_actions_port_id": "4",
                "flow_actions_port_node_id": "00:00:00:00:00:00:00:03",
                "flow_actions_port_node_type": "OF",
                "flow_actions_port_type": "OF",
                "flow_hardTimeout": "0",
                "flow_idleTimeout": "0",
                "flow_priority": "1"}, None),
        ]
        self._test_for_meter('switch.flow.duration_nanoseconds', expected_data)

    def test_meter_switch_flow_packets(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '0',
                'flow_id': '0',
                "flow_match_matchField[0]_type": "DL_TYPE",
                "flow_match_matchField[0]_value": "2048",
                "flow_match_matchField[1]_mask": "255.255.255.255",
                "flow_match_matchField[1]_type": "NW_DST",
                "flow_match_matchField[1]_value": "1.1.1.1",
                "flow_actions_@type": "output",
                "flow_actions_port_id": "3",
                "flow_actions_port_node_id": "00:00:00:00:00:00:00:02",
                "flow_actions_port_node_type": "OF",
                "flow_actions_port_type": "OF",
                "flow_hardTimeout": "0",
                "flow_idleTimeout": "0",
                "flow_priority": "1"}, None),
            (30, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '1',
                'flow_id': '0',
                "flow_match_matchField[0]_type": "DL_TYPE",
                "flow_match_matchField[0]_value": "2048",
                "flow_match_matchField[1]_mask": "255.255.255.255",
                "flow_match_matchField[1]_type": "NW_DST",
                "flow_match_matchField[1]_value": "1.1.1.2",
                "flow_actions_@type": "output",
                "flow_actions_port_id": "4",
                "flow_actions_port_node_id": "00:00:00:00:00:00:00:03",
                "flow_actions_port_node_type": "OF",
                "flow_actions_port_type": "OF",
                "flow_hardTimeout": "0",
                "flow_idleTimeout": "0",
                "flow_priority": "1"}, None),
        ]
        self._test_for_meter('switch.flow.packets', expected_data)

    def test_meter_switch_flow_bytes(self):
        expected_data = [
            (0, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '0',
                'flow_id': '0',
                "flow_match_matchField[0]_type": "DL_TYPE",
                "flow_match_matchField[0]_value": "2048",
                "flow_match_matchField[1]_mask": "255.255.255.255",
                "flow_match_matchField[1]_type": "NW_DST",
                "flow_match_matchField[1]_value": "1.1.1.1",
                "flow_actions_@type": "output",
                "flow_actions_port_id": "3",
                "flow_actions_port_node_id": "00:00:00:00:00:00:00:02",
                "flow_actions_port_node_type": "OF",
                "flow_actions_port_type": "OF",
                "flow_hardTimeout": "0",
                "flow_idleTimeout": "0",
                "flow_priority": "1"}, None),
            (89, "00:00:00:00:00:00:00:02", {
                'controller': 'OpenDaylight',
                'container': 'default',
                'table_id': '1',
                'flow_id': '0',
                "flow_match_matchField[0]_type": "DL_TYPE",
                "flow_match_matchField[0]_value": "2048",
                "flow_match_matchField[1]_mask": "255.255.255.255",
                "flow_match_matchField[1]_type": "NW_DST",
                "flow_match_matchField[1]_value": "1.1.1.2",
                "flow_actions_@type": "output",
                "flow_actions_port_id": "4",
                "flow_actions_port_node_id": "00:00:00:00:00:00:00:03",
                "flow_actions_port_node_type": "OF",
                "flow_actions_port_type": "OF",
                "flow_hardTimeout": "0",
                "flow_idleTimeout": "0",
                "flow_priority": "1"}, None),
        ]
        self._test_for_meter('switch.flow.bytes', expected_data)
