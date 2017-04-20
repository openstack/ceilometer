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
from neutronclient.v2_0 import client
from oslotest import base

from ceilometer import neutron_client
from ceilometer import service


class TestNeutronClientLBaaSV2(base.BaseTestCase):

    def setUp(self):
        super(TestNeutronClientLBaaSV2, self).setUp()
        conf = service.prepare_service([], [])
        self.nc = neutron_client.Client(conf)

    @staticmethod
    def fake_list_lbaas_pools():
        return {
            'pools': [{
                'lb_algorithm': 'ROUND_ROBIN',
                'protocol': 'HTTP',
                'description': 'simple pool',
                'admin_state_up': True,
                'tenant_id': '1a3e005cf9ce40308c900bcb08e5320c',
                'healthmonitor_id': None,
                'listeners': [{
                    'id': "35cb8516-1173-4035-8dae-0dae3453f37f"
                    }
                ],
                'members': [{
                    'id': 'fcf23bde-8cf9-4616-883f-208cebcbf858'}
                ],
                'id': '4c0a0a5f-cf8f-44b7-b912-957daa8ce5e5',
                'name': 'pool1'
                }]
            }

    @staticmethod
    def fake_list_lbaas_members():
        return {
            'members': [{
                'weight': 1,
                'admin_state_up': True,
                'subnet_id': '013d3059-87a4-45a5-91e9-d721068ae0b2',
                'tenant_id': '1a3e005cf9ce40308c900bcb08e5320c',
                'address': '10.0.0.8',
                'protocol_port': 80,
                'id': 'fcf23bde-8cf9-4616-883f-208cebcbf858'
                }]
            }

    @staticmethod
    def fake_list_lbaas_healthmonitors():
        return {
            'healthmonitors': [{
                'admin_state_up': True,
                'tenant_id': '6f3584d5754048a18e30685362b88411',
                'delay': 1,
                'expected_codes': '200,201,202',
                'max_retries': 5,
                'http_method': 'GET',
                'timeout': 1,
                'pools': [{
                    'id': '74aa2010-a59f-4d35-a436-60a6da882819'
                    }],
                'url_path': '/index.html',
                'type': 'HTTP',
                'id': '0a9ac99d-0a09-4b18-8499-a0796850279a'
                }]
            }

    @staticmethod
    def fake_show_listener():
        return {
            'listener': {
                'default_pool_id': None,
                'protocol': 'HTTP',
                'description': '',
                'admin_state_up': True,
                'loadbalancers': [{
                    'id': 'a9729389-6147-41a3-ab22-a24aed8692b2'
                    }],
                'tenant_id': '3e4d8bec50a845fcb09e03a4375c691d',
                'connection_limit': 100,
                'protocol_port': 80,
                'id': '35cb8516-1173-4035-8dae-0dae3453f37f',
                'name': ''
                }
            }

    @staticmethod
    def fake_retrieve_loadbalancer_status():
        return {
            'statuses': {
                'loadbalancer': {
                    'operating_status': 'ONLINE',
                    'provisioning_status': 'ACTIVE',
                    'listeners': [{
                        'id': '35cb8516-1173-4035-8dae-0dae3453f37f',
                        'operating_status': 'ONLINE',
                        'provisioning_status': 'ACTIVE',
                        'pools': [{
                            'id': '4c0a0a5f-cf8f-44b7-b912-957daa8ce5e5',
                            'operating_status': 'ONLINE',
                            'provisioning_status': 'ACTIVE',
                            'members': [{
                                'id': 'fcf23bde-8cf9-4616-883f-208cebcbf858',
                                'operating_status': 'ONLINE',
                                'provisioning_status': 'ACTIVE'
                                }],
                            'healthmonitor': {
                                'id': '785131d2-8f7b-4fee-a7e7-3196e11b4518',
                                'provisioning_status': 'ACTIVE'
                                }
                            }]
                        }]
                    }
                }
            }

    @staticmethod
    def fake_retrieve_loadbalancer_status_complex():
        return {
            'statuses': {
                'loadbalancer': {
                    'operating_status': 'ONLINE',
                    'provisioning_status': 'ACTIVE',
                    'listeners': [{
                        'id': '35cb8516-1173-4035-8dae-0dae3453f37f',
                        'operating_status': 'ONLINE',
                        'provisioning_status': 'ACTIVE',
                        'pools': [{
                            'id': '4c0a0a5f-cf8f-44b7-b912-957daa8ce5e5',
                            'operating_status': 'ONLINE',
                            'provisioning_status': 'ACTIVE',
                            'members': [{
                                'id': 'fcf23bde-8cf9-4616-883f-208cebcbf858',
                                'operating_status': 'ONLINE',
                                'provisioning_status': 'ACTIVE'
                                },
                                {
                                'id': 'fcf23bde-8cf9-4616-883f-208cebcbf969',
                                'operating_status': 'OFFLINE',
                                'provisioning_status': 'ACTIVE'
                                }],
                            'healthmonitor': {
                                'id': '785131d2-8f7b-4fee-a7e7-3196e11b4518',
                                'provisioning_status': 'ACTIVE'
                                }
                            },
                            {
                            'id': '4c0a0a5f-cf8f-44b7-b912-957daa8ce6f6',
                            'operating_status': 'OFFLINE',
                            'provisioning_status': 'ACTIVE',
                            'members': [{
                                'id': 'fcf23bde-8cf9-4616-883f-208cebcbfa7a',
                                'operating_status': 'ONLINE',
                                'provisioning_status': 'ACTIVE'
                                }],
                            'healthmonitor': {
                                'id': '785131d2-8f7b-4fee-a7e7-3196e11b4629',
                                'provisioning_status': 'ACTIVE'
                                }
                            }]
                        },
                        {
                        'id': '35cb8516-1173-4035-8dae-0dae3453f48e',
                        'operating_status': 'OFFLINE',
                        'provisioning_status': 'ACTIVE',
                        'pools': [{
                            'id': '4c0a0a5f-cf8f-44b7-b912-957daa8ce7g7',
                            'operating_status': 'ONLINE',
                            'provisioning_status': 'ACTIVE',
                            'members': [{
                                'id': 'fcf23bde-8cf9-4616-883f-208cebcbfb8b',
                                'operating_status': 'ONLINE',
                                'provisioning_status': 'ACTIVE'
                                }],
                            'healthmonitor': {
                                'id': '785131d2-8f7b-4fee-a7e7-3196e11b473a',
                                'provisioning_status': 'ACTIVE'
                                }
                            }]
                        }]
                    }
                }
            }

    @staticmethod
    def fake_list_lbaas_listeners():
        return {
            'listeners': [{
                'default_pool_id': None,
                'protocol': 'HTTP',
                'description': '',
                'admin_state_up': True,
                'loadbalancers': [{
                    'id': 'a9729389-6147-41a3-ab22-a24aed8692b2'
                    }],
                'tenant_id': '3e4d8bec50a845fcb09e03a4375c691d',
                'connection_limit': 100,
                'protocol_port': 80,
                'id': '35cb8516-1173-4035-8dae-0dae3453f37f',
                'name': 'listener_one'
                }]}

    @mock.patch.object(client.Client,
                       'list_lbaas_pools')
    @mock.patch.object(client.Client,
                       'show_listener')
    @mock.patch.object(neutron_client.Client,
                       '_retrieve_loadbalancer_status_tree')
    def test_list_pools_v2(self, mock_status, mock_show, mock_list):
        mock_status.return_value = self.fake_retrieve_loadbalancer_status()
        mock_show.return_value = self.fake_show_listener()
        mock_list.return_value = self.fake_list_lbaas_pools()
        pools = self.nc.list_pools_v2()
        self.assertEqual(1, len(pools))
        for pool in pools:
            self.assertEqual('ONLINE', pool['status'])
            self.assertEqual('ROUND_ROBIN', pool['lb_method'])

    @mock.patch.object(client.Client,
                       'list_lbaas_pools')
    @mock.patch.object(client.Client,
                       'list_lbaas_members')
    @mock.patch.object(client.Client,
                       'show_listener')
    @mock.patch.object(neutron_client.Client,
                       '_retrieve_loadbalancer_status_tree')
    def test_list_members_v2(self, mock_status, mock_show, mock_list_members,
                             mock_list_pools):
        mock_status.return_value = self.fake_retrieve_loadbalancer_status()
        mock_show.return_value = self.fake_show_listener()
        mock_list_pools.return_value = self.fake_list_lbaas_pools()
        mock_list_members.return_value = self.fake_list_lbaas_members()
        members = self.nc.list_members_v2()
        self.assertEqual(1, len(members))
        for member in members:
            self.assertEqual('ONLINE', member['status'])
            self.assertEqual('4c0a0a5f-cf8f-44b7-b912-957daa8ce5e5',
                             member['pool_id'])

    @mock.patch.object(client.Client,
                       'list_lbaas_healthmonitors')
    def test_list_health_monitors_v2(self, mock_list_healthmonitors):
        mock_list_healthmonitors.return_value = (
            self.fake_list_lbaas_healthmonitors())
        healthmonitors = self.nc.list_health_monitors_v2()
        self.assertEqual(1, len(healthmonitors))
        for healthmonitor in healthmonitors:
            self.assertEqual(5, healthmonitor['max_retries'])

    @mock.patch.object(neutron_client.Client,
                       '_retrieve_loadbalancer_status_tree')
    def test_get_member_status(self, mock_status):
        mock_status.return_value = (
            self.fake_retrieve_loadbalancer_status_complex())
        loadbalancer_id = '5b1b1b6e-cf8f-44b7-b912-957daa8ce5e5'
        listener_id = '35cb8516-1173-4035-8dae-0dae3453f37f'
        pool_id = '4c0a0a5f-cf8f-44b7-b912-957daa8ce5e5'
        parent_id = [listener_id, pool_id]
        result_status = self.nc._get_member_status(loadbalancer_id,
                                                   parent_id)
        expected_keys = ['fcf23bde-8cf9-4616-883f-208cebcbf858',
                         'fcf23bde-8cf9-4616-883f-208cebcbf969']
        excepted_status = {
            'fcf23bde-8cf9-4616-883f-208cebcbf858': 'ONLINE',
            'fcf23bde-8cf9-4616-883f-208cebcbf969': 'OFFLINE'}

        for key in result_status.keys():
            self.assertIn(key, expected_keys)
            self.assertEqual(excepted_status[key], result_status[key])

    @mock.patch.object(neutron_client.Client,
                       '_retrieve_loadbalancer_status_tree')
    def test_get_pool_status(self, mock_status):
        mock_status.return_value = (
            self.fake_retrieve_loadbalancer_status_complex())
        loadbalancer_id = '5b1b1b6e-cf8f-44b7-b912-957daa8ce5e5'
        parent_id = '35cb8516-1173-4035-8dae-0dae3453f37f'
        result_status = self.nc._get_pool_status(loadbalancer_id,
                                                 parent_id)
        expected_keys = ['4c0a0a5f-cf8f-44b7-b912-957daa8ce5e5',
                         '4c0a0a5f-cf8f-44b7-b912-957daa8ce6f6']
        excepted_status = {
            '4c0a0a5f-cf8f-44b7-b912-957daa8ce5e5': 'ONLINE',
            '4c0a0a5f-cf8f-44b7-b912-957daa8ce6f6': 'OFFLINE'}

        for key in result_status.keys():
            self.assertIn(key, expected_keys)
            self.assertEqual(excepted_status[key], result_status[key])

    @mock.patch.object(neutron_client.Client,
                       '_retrieve_loadbalancer_status_tree')
    def test_get_listener_status(self, mock_status):
        mock_status.return_value = (
            self.fake_retrieve_loadbalancer_status_complex())
        loadbalancer_id = '5b1b1b6e-cf8f-44b7-b912-957daa8ce5e5'
        result_status = self.nc._get_listener_status(loadbalancer_id)
        expected_keys = ['35cb8516-1173-4035-8dae-0dae3453f37f',
                         '35cb8516-1173-4035-8dae-0dae3453f48e']
        excepted_status = {
            '35cb8516-1173-4035-8dae-0dae3453f37f': 'ONLINE',
            '35cb8516-1173-4035-8dae-0dae3453f48e': 'OFFLINE'}

        for key in result_status.keys():
            self.assertIn(key, expected_keys)
            self.assertEqual(excepted_status[key], result_status[key])

    @mock.patch.object(client.Client,
                       'list_listeners')
    @mock.patch.object(neutron_client.Client,
                       '_retrieve_loadbalancer_status_tree')
    def test_list_listener(self, mock_status, mock_list_listeners):
        mock_list_listeners.return_value = (
            self.fake_list_lbaas_listeners())
        mock_status.return_value = (
            self.fake_retrieve_loadbalancer_status())
        listeners = self.nc.list_listener()
        expected_key = '35cb8516-1173-4035-8dae-0dae3453f37f'
        expected_status = 'ONLINE'
        self.assertEqual(1, len(listeners))
        self.assertEqual(expected_key, listeners[0]['id'])
        self.assertEqual(expected_status, listeners[0]['operating_status'])
