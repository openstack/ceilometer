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

import mock
from oslotest import base
from six.moves.urllib import parse as urlparse

from ceilometer.network.statistics.opencontrail import driver
from ceilometer import service


class TestOpencontrailDriver(base.BaseTestCase):

    def setUp(self):
        super(TestOpencontrailDriver, self).setUp()

        self.nc_ports = mock.patch('ceilometer.neutron_client'
                                   '.Client.port_get_all',
                                   return_value=self.fake_ports())
        self.nc_ports.start()

        self.CONF = service.prepare_service([], [])
        self.driver = driver.OpencontrailDriver(self.CONF)
        self.parse_url = urlparse.ParseResult('opencontrail',
                                              '127.0.0.1:8143',
                                              '/', None, None, None)
        self.params = {'password': ['admin'],
                       'scheme': ['http'],
                       'username': ['admin'],
                       'verify_ssl': ['false'],
                       'resource': ['if_stats_list']}

    @staticmethod
    def fake_ports():
        return [{'admin_state_up': True,
                 'device_owner': 'compute:None',
                 'device_id': '674e553b-8df9-4321-87d9-93ba05b93558',
                 'extra_dhcp_opts': [],
                 'id': '96d49cc3-4e01-40ce-9cac-c0e32642a442',
                 'mac_address': 'fa:16:3e:c5:35:93',
                 'name': '',
                 'network_id': '298a3088-a446-4d5a-bad8-f92ecacd786b',
                 'status': 'ACTIVE',
                 'tenant_id': '89271fa581ab4380bf172f868c3615f9'}]

    @staticmethod
    def fake_port_stats():
        return {"value": [{
            "name": "c588ebb7-ae52-485a-9f0c-b2791c5da196",
            "value": {
                "UveVirtualMachineAgent": {
                    "if_stats_list": [{
                        "out_bytes": 22,
                        "in_bandwidth_usage": 0,
                        "in_bytes": 23,
                        "out_bandwidth_usage": 0,
                        "out_pkts": 5,
                        "in_pkts": 6,
                        "name": ("default-domain:demo:"
                                 "96d49cc3-4e01-40ce-9cac-c0e32642a442")
                    }],
                    "fip_stats_list": [{
                        "in_bytes": 33,
                        "iface_name": ("default-domain:demo:"
                                       "96d49cc3-4e01-40ce-9cac-c0e32642a442"),
                        "out_bytes": 44,
                        "out_pkts": 10,
                        "virtual_network": "default-domain:openstack:public",
                        "in_pkts": 11,
                        "ip_address": "1.1.1.1"
                    }]
                }}}]}

    @staticmethod
    def fake_port_stats_with_node():
        return {"value": [{
            "name": "c588ebb7-ae52-485a-9f0c-b2791c5da196",
            "value": {
                "UveVirtualMachineAgent": {
                    "if_stats_list": [
                        [[{
                            "out_bytes": 22,
                            "in_bandwidth_usage": 0,
                            "in_bytes": 23,
                            "out_bandwidth_usage": 0,
                            "out_pkts": 5,
                            "in_pkts": 6,
                            "name": ("default-domain:demo:"
                                     "96d49cc3-4e01-40ce-9cac-c0e32642a442")
                        }], 'node1'],
                        [[{
                            "out_bytes": 22,
                            "in_bandwidth_usage": 0,
                            "in_bytes": 23,
                            "out_bandwidth_usage": 0,
                            "out_pkts": 4,
                            "in_pkts": 13,
                            "name": ("default-domain:demo:"
                                     "96d49cc3-4e01-40ce-9cac-c0e32642a442")}],
                            'node2']
                    ]
                }}}]}

    def _test_meter(self, meter_name, expected, fake_port_stats=None):
        if not fake_port_stats:
            fake_port_stats = self.fake_port_stats()
        with mock.patch('ceilometer.network.'
                        'statistics.opencontrail.'
                        'client.NetworksAPIClient.'
                        'get_vm_statistics',
                        return_value=fake_port_stats) as port_stats:

            samples = self.driver.get_sample_data(meter_name, self.parse_url,
                                                  self.params, {})

            self.assertEqual(expected, [s for s in samples])

            port_stats.assert_called_with('*')

    def test_switch_port_receive_packets_with_node(self):
        expected = [(6,
                     '96d49cc3-4e01-40ce-9cac-c0e32642a442',
                     {'device_owner_id':
                      '674e553b-8df9-4321-87d9-93ba05b93558',
                      'domain': 'default-domain',
                      'network_id': '298a3088-a446-4d5a-bad8-f92ecacd786b',
                      'project': 'demo',
                      'project_id': '89271fa581ab4380bf172f868c3615f9',
                      'resource': 'if_stats_list'},
                     None),
                    (13,
                     '96d49cc3-4e01-40ce-9cac-c0e32642a442',
                     {'device_owner_id':
                      '674e553b-8df9-4321-87d9-93ba05b93558',
                      'domain': 'default-domain',
                      'network_id': '298a3088-a446-4d5a-bad8-f92ecacd786b',
                      'project': 'demo',
                      'project_id': '89271fa581ab4380bf172f868c3615f9',
                      'resource': 'if_stats_list'},
                     None)]
        self._test_meter('switch.port.receive.packets', expected,
                         self.fake_port_stats_with_node())

    def test_switch_port_receive_packets(self):
        expected = [(6,
                     '96d49cc3-4e01-40ce-9cac-c0e32642a442',
                     {'device_owner_id':
                      '674e553b-8df9-4321-87d9-93ba05b93558',
                      'domain': 'default-domain',
                      'network_id': '298a3088-a446-4d5a-bad8-f92ecacd786b',
                      'project': 'demo',
                      'project_id': '89271fa581ab4380bf172f868c3615f9',
                      'resource': 'if_stats_list'},
                     None)]
        self._test_meter('switch.port.receive.packets', expected)

    def test_switch_port_transmit_packets(self):
        expected = [(5,
                     '96d49cc3-4e01-40ce-9cac-c0e32642a442',
                     {'device_owner_id':
                      '674e553b-8df9-4321-87d9-93ba05b93558',
                      'domain': 'default-domain',
                      'network_id': '298a3088-a446-4d5a-bad8-f92ecacd786b',
                      'project': 'demo',
                      'project_id': '89271fa581ab4380bf172f868c3615f9',
                      'resource': 'if_stats_list'},
                     None)]
        self._test_meter('switch.port.transmit.packets', expected)

    def test_switch_port_receive_bytes(self):
        expected = [(23,
                     '96d49cc3-4e01-40ce-9cac-c0e32642a442',
                     {'device_owner_id':
                      '674e553b-8df9-4321-87d9-93ba05b93558',
                      'domain': 'default-domain',
                      'network_id': '298a3088-a446-4d5a-bad8-f92ecacd786b',
                      'project': 'demo',
                      'project_id': '89271fa581ab4380bf172f868c3615f9',
                      'resource': 'if_stats_list'},
                     None)]
        self._test_meter('switch.port.receive.bytes', expected)

    def test_switch_port_transmit_bytes(self):
        expected = [(22,
                     '96d49cc3-4e01-40ce-9cac-c0e32642a442',
                     {'device_owner_id':
                      '674e553b-8df9-4321-87d9-93ba05b93558',
                      'domain': 'default-domain',
                      'network_id': '298a3088-a446-4d5a-bad8-f92ecacd786b',
                      'project': 'demo',
                      'project_id': '89271fa581ab4380bf172f868c3615f9',
                      'resource': 'if_stats_list'},
                     None)]
        self._test_meter('switch.port.transmit.bytes', expected)

    def test_switch_port_receive_packets_fip(self):
        self.params['resource'] = ['fip_stats_list']
        expected = [(11,
                     '96d49cc3-4e01-40ce-9cac-c0e32642a442',
                     {'device_owner_id':
                      '674e553b-8df9-4321-87d9-93ba05b93558',
                      'domain': 'default-domain',
                      'network_id': '298a3088-a446-4d5a-bad8-f92ecacd786b',
                      'project': 'demo',
                      'project_id': '89271fa581ab4380bf172f868c3615f9',
                      'resource': 'fip_stats_list'},
                     None)]
        self._test_meter('switch.port.receive.packets', expected)

    def test_switch_port_transmit_packets_fip(self):
        self.params['resource'] = ['fip_stats_list']
        expected = [(10,
                     '96d49cc3-4e01-40ce-9cac-c0e32642a442',
                     {'device_owner_id':
                      '674e553b-8df9-4321-87d9-93ba05b93558',
                      'domain': 'default-domain',
                      'network_id': '298a3088-a446-4d5a-bad8-f92ecacd786b',
                      'project': 'demo',
                      'project_id': '89271fa581ab4380bf172f868c3615f9',
                      'resource': 'fip_stats_list'},
                     None)]
        self._test_meter('switch.port.transmit.packets', expected)

    def test_switch_port_receive_bytes_fip(self):
        self.params['resource'] = ['fip_stats_list']
        expected = [(33,
                     '96d49cc3-4e01-40ce-9cac-c0e32642a442',
                     {'device_owner_id':
                      '674e553b-8df9-4321-87d9-93ba05b93558',
                      'domain': 'default-domain',
                      'network_id': '298a3088-a446-4d5a-bad8-f92ecacd786b',
                      'project': 'demo',
                      'project_id': '89271fa581ab4380bf172f868c3615f9',
                      'resource': 'fip_stats_list'},
                     None)]
        self._test_meter('switch.port.receive.bytes', expected)

    def test_switch_port_transmit_bytes_fip(self):
        self.params['resource'] = ['fip_stats_list']
        expected = [(44,
                     '96d49cc3-4e01-40ce-9cac-c0e32642a442',
                     {'device_owner_id':
                      '674e553b-8df9-4321-87d9-93ba05b93558',
                      'domain': 'default-domain',
                      'network_id': '298a3088-a446-4d5a-bad8-f92ecacd786b',
                      'project': 'demo',
                      'project_id': '89271fa581ab4380bf172f868c3615f9',
                      'resource': 'fip_stats_list'},
                     None)]
        self._test_meter('switch.port.transmit.bytes', expected)

    def test_switch_port_transmit_bytes_non_existing_network(self):
        self.params['virtual_network'] = ['aaa']
        self.params['resource'] = ['fip_stats_list']
        self._test_meter('switch.port.transmit.bytes', [])
