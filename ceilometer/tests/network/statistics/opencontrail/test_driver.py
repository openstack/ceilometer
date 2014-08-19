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

import mock
from oslotest import base
from six.moves.urllib import parse as urlparse

from ceilometer.network.statistics.opencontrail import driver


class TestOpencontrailDriver(base.BaseTestCase):

    def setUp(self):
        super(TestOpencontrailDriver, self).setUp()

        self.nc_ports = mock.patch('ceilometer.neutron_client'
                                   '.Client.port_get_all',
                                   return_value=self.fake_ports())
        self.nc_ports.start()

        self.nc_networks = mock.patch('ceilometer.neutron_client'
                                      '.Client.network_get_all',
                                      return_value=self.fake_networks())
        self.nc_networks.start()

        self.driver = driver.OpencontrailDriver()
        self.parse_url = urlparse.ParseResult('opencontrail',
                                              '127.0.0.1:8143',
                                              '/', None, None, None)
        self.params = {'password': ['admin'],
                       'scheme': ['http'],
                       'username': ['admin'],
                       'verify_ssl': ['false']}

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
    def fake_networks():
        return [{'admin_state_up': True,
                 'id': '298a3088-a446-4d5a-bad8-f92ecacd786b',
                 'name': 'public',
                 'provider:network_type': 'gre',
                 'provider:physical_network': None,
                 'provider:segmentation_id': 2,
                 'router:external': True,
                 'shared': False,
                 'status': 'ACTIVE',
                 'subnets': [u'c4b6f5b8-3508-4896-b238-a441f25fb492'],
                 'tenant_id': '62d6f08bbd3a44f6ad6f00ca15cce4e5'}]

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
                        "name": ("674e553b-8df9-4321-87d9-93ba05b93558:"
                                 "96d49cc3-4e01-40ce-9cac-c0e32642a442")
                    }]}}}]}

    def _test_meter(self, meter_name, expected):
        with mock.patch('ceilometer.network.'
                        'statistics.opencontrail.'
                        'client.NetworksAPIClient.'
                        'get_port_statistics',
                        return_value=self.fake_port_stats()) as port_stats:

            samples = self.driver.get_sample_data(meter_name, self.parse_url,
                                                  self.params, {})

            self.assertEqual(expected, [s for s in samples])

            net_id = '298a3088-a446-4d5a-bad8-f92ecacd786b'
            port_stats.assert_called_with(net_id)

    def test_switch_port_receive_packets(self):
        expected = [
            (6,
             '96d49cc3-4e01-40ce-9cac-c0e32642a442',
             {'device_owner_id': '674e553b-8df9-4321-87d9-93ba05b93558',
              'network_id': '298a3088-a446-4d5a-bad8-f92ecacd786b',
              'tenant_id': '89271fa581ab4380bf172f868c3615f9'},
             mock.ANY)]
        self._test_meter('switch.port.receive.packets', expected)

    def test_switch_port_transmit_packets(self):
        expected = [
            (5,
             '96d49cc3-4e01-40ce-9cac-c0e32642a442',
             {'device_owner_id': '674e553b-8df9-4321-87d9-93ba05b93558',
              'network_id': '298a3088-a446-4d5a-bad8-f92ecacd786b',
              'tenant_id': '89271fa581ab4380bf172f868c3615f9'},
             mock.ANY)]
        self._test_meter('switch.port.transmit.packets', expected)

    def test_switch_port_receive_bytes(self):
        expected = [
            (23,
             '96d49cc3-4e01-40ce-9cac-c0e32642a442',
             {'device_owner_id': '674e553b-8df9-4321-87d9-93ba05b93558',
              'network_id': '298a3088-a446-4d5a-bad8-f92ecacd786b',
              'tenant_id': '89271fa581ab4380bf172f868c3615f9'},
             mock.ANY)]
        self._test_meter('switch.port.receive.bytes', expected)

    def test_switch_port_transmit_bytes(self):
        expected = [
            (22,
             '96d49cc3-4e01-40ce-9cac-c0e32642a442',
             {'device_owner_id': '674e553b-8df9-4321-87d9-93ba05b93558',
              'network_id': '298a3088-a446-4d5a-bad8-f92ecacd786b',
              'tenant_id': '89271fa581ab4380bf172f868c3615f9'},
             mock.ANY)]
        self._test_meter('switch.port.transmit.bytes', expected)
