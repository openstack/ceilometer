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

from ceilometer import neutron_client
from ceilometer import service


class TestNeutronClient(base.BaseTestCase):

    def setUp(self):
        super(TestNeutronClient, self).setUp()
        self.CONF = service.prepare_service([], [])
        self.nc = neutron_client.Client(self.CONF)
        self.nc.lb_version = 'v1'

    @staticmethod
    def fake_ports_list():
        return {'ports':
                [{'admin_state_up': True,
                  'device_id': '674e553b-8df9-4321-87d9-93ba05b93558',
                  'device_owner': 'network:router_gateway',
                  'extra_dhcp_opts': [],
                  'id': '96d49cc3-4e01-40ce-9cac-c0e32642a442',
                  'mac_address': 'fa:16:3e:c5:35:93',
                  'name': '',
                  'network_id': '298a3088-a446-4d5a-bad8-f92ecacd786b',
                  'status': 'ACTIVE',
                  'tenant_id': '89271fa581ab4380bf172f868c3615f9'},
                 ]}

    def test_port_get_all(self):
        with mock.patch.object(self.nc.client, 'list_ports',
                               side_effect=self.fake_ports_list):
            ports = self.nc.port_get_all()

        self.assertEqual(1, len(ports))
        self.assertEqual('96d49cc3-4e01-40ce-9cac-c0e32642a442',
                         ports[0]['id'])

    @staticmethod
    def fake_networks_list():
        return {'networks':
                [{'admin_state_up': True,
                  'id': '298a3088-a446-4d5a-bad8-f92ecacd786b',
                  'name': 'public',
                  'provider:network_type': 'gre',
                  'provider:physical_network': None,
                  'provider:segmentation_id': 2,
                  'router:external': True,
                  'shared': False,
                  'status': 'ACTIVE',
                  'subnets': [u'c4b6f5b8-3508-4896-b238-a441f25fb492'],
                  'tenant_id': '62d6f08bbd3a44f6ad6f00ca15cce4e5'},
                 ]}

    @staticmethod
    def fake_pool_list():
        return {'pools': [{'status': 'ACTIVE',
                           'lb_method': 'ROUND_ROBIN',
                           'protocol': 'HTTP',
                           'description': '',
                           'health_monitors': [],
                           'members': [],
                           'status_description': None,
                           'id': 'ce73ad36-437d-4c84-aee1-186027d3da9a',
                           'vip_id': 'cd6a6fee-e2fa-4e6c-b3c2-bfbe395752c1',
                           'name': 'mylb',
                           'admin_state_up': True,
                           'subnet_id': 'bbe3d818-bdcb-4e4b-b47f-5650dc8a9d7a',
                           'tenant_id': 'a4eb9f4938bb418bbc4f8eb31802fefa',
                           'health_monitors_status': []},
                          ]}

    def test_pool_list(self):
        with mock.patch.object(self.nc.client, 'list_pools',
                               side_effect=self.fake_pool_list):
            pools = self.nc.pool_get_all()

        self.assertEqual(1, len(pools))
        self.assertEqual('ce73ad36-437d-4c84-aee1-186027d3da9a',
                         pools[0]['id'])

    @staticmethod
    def fake_vip_list():
        return {'vips': [{'status': 'ACTIVE',
                          'status_description': None,
                          'protocol': 'HTTP',
                          'description': '',
                          'admin_state_up': True,
                          'subnet_id': 'bbe3d818-bdcb-4e4b-b47f-5650dc8a9d7a',
                          'tenant_id': 'a4eb9f4938bb418bbc4f8eb31802fefa',
                          'connection_limit': -1,
                          'pool_id': 'ce73ad36-437d-4c84-aee1-186027d3da9a',
                          'session_persistence': None,
                          'address': '10.0.0.2',
                          'protocol_port': 80,
                          'port_id': '3df3c4de-b32e-4ca1-a7f4-84323ba5f291',
                          'id': 'cd6a6fee-e2fa-4e6c-b3c2-bfbe395752c1',
                          'name': 'myvip'},
                         ]}

    def test_vip_list(self):
        with mock.patch.object(self.nc.client, 'list_vips',
                               side_effect=self.fake_vip_list):
            vips = self.nc.vip_get_all()

        self.assertEqual(1, len(vips))
        self.assertEqual('cd6a6fee-e2fa-4e6c-b3c2-bfbe395752c1',
                         vips[0]['id'])

    @staticmethod
    def fake_member_list():
        return {'members': [{'status': 'ACTIVE',
                             'protocol_port': 80,
                             'weight': 1,
                             'admin_state_up': True,
                             'tenant_id': 'a4eb9f4938bb418bbc4f8eb31802fefa',
                             'pool_id': 'ce73ad36-437d-4c84-aee1-186027d3da9a',
                             'address': '10.0.0.3',
                             'status_description': None,
                             'id': '290b61eb-07bc-4372-9fbf-36459dd0f96b'},
                            ]}

    def test_member_list(self):
        with mock.patch.object(self.nc.client, 'list_members',
                               side_effect=self.fake_member_list):
            members = self.nc.member_get_all()

        self.assertEqual(1, len(members))
        self.assertEqual('290b61eb-07bc-4372-9fbf-36459dd0f96b',
                         members[0]['id'])

    @staticmethod
    def fake_monitors_list():
        return {'health_monitors':
                [{'id': '34ae33e1-0035-49e2-a2ca-77d5d3fab365',
                  'admin_state_up': True,
                  'tenant_id': "d5d2817dae6b42159be9b665b64beb0e",
                  'delay': 2,
                  'max_retries': 5,
                  'timeout': 5,
                  'pools': [],
                  'type': 'PING',
                  }]}

    def test_monitor_list(self):
        with mock.patch.object(self.nc.client, 'list_health_monitors',
                               side_effect=self.fake_monitors_list):
            monitors = self.nc.health_monitor_get_all()

        self.assertEqual(1, len(monitors))
        self.assertEqual('34ae33e1-0035-49e2-a2ca-77d5d3fab365',
                         monitors[0]['id'])

    @staticmethod
    def fake_pool_stats(fake_pool):
        return {'stats':
                [{'active_connections': 1,
                  'total_connections': 2,
                  'bytes_in': 3,
                  'bytes_out': 4
                  }]}

    def test_pool_stats(self):
        with mock.patch.object(self.nc.client, 'retrieve_pool_stats',
                               side_effect=self.fake_pool_stats):
            stats = self.nc.pool_stats('fake_pool')['stats']

        self.assertEqual(1, len(stats))
        self.assertEqual(1, stats[0]['active_connections'])
        self.assertEqual(2, stats[0]['total_connections'])
        self.assertEqual(3, stats[0]['bytes_in'])
        self.assertEqual(4, stats[0]['bytes_out'])

    def test_v1_list_loadbalancer_returns_empty_list(self):
        self.assertEqual([], self.nc.list_loadbalancer())

    def test_v1_list_listener_returns_empty_list(self):
        self.assertEqual([], self.nc.list_listener())
