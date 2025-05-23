#
# Copyright 2014 Cisco Systems,Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
from unittest import mock

import fixtures
from oslotest import base

from ceilometer.network.services import discovery
from ceilometer.network.services import vpnaas
from ceilometer.polling import manager
from ceilometer.polling import plugin_base
from ceilometer import service


class _BaseTestVPNPollster(base.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.addCleanup(mock.patch.stopall)
        self.CONF = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, self.CONF)
        plugin_base._get_keystone = mock.Mock()
        catalog = (plugin_base._get_keystone.session.auth.get_access.
                   return_value.service_catalog)
        catalog.get_endpoints = mock.MagicMock(
            return_value={'network': mock.ANY})


class TestVPNServicesPollster(_BaseTestVPNPollster):

    def setUp(self):
        super().setUp()
        self.pollster = vpnaas.VPNServicesPollster(self.CONF)
        self.fake_vpn = self.fake_get_vpn_service()
        self.useFixture(fixtures.MockPatch('ceilometer.neutron_client.Client.'
                                           'vpn_get_all',
                                           return_value=self.fake_vpn))

    @staticmethod
    def fake_get_vpn_service():
        return [{'status': 'ACTIVE',
                 'name': 'myvpn1',
                 'description': '',
                 'admin_state_up': True,
                 'id': 'fdde3d818-fdcb-fg4b-de7f-6750dc8a9d7a',
                 'subnet_id': 'bbe3d818-bdcb-4e4b-b47f-5650dc8a9d7a',
                 'tenant_id': 'a4eb9f4938bb418bbc4f8eb31802fefa',
                 'router_id': 'ade3d818-fdcb-fg4b-de7f-6750dc8a9d7a'},
                {'status': 'INACTIVE',
                 'name': 'myvpn2',
                 'description': '',
                 'admin_state_up': True,
                 'id': 'cdde3d818-fdcb-fg4b-de7f-6750dc8a9d7a',
                 'subnet_id': 'bbe3d818-bdcb-4e4b-b47f-5650dc8a9d7a',
                 'tenant_id': 'a4eb9f4938bb418bbc4f8eb31802fefa',
                 'router_id': 'ade3d818-fdcb-fg4b-de7f-6750dc8a9d7a'},
                {'status': 'PENDING_CREATE',
                 'name': 'myvpn3',
                 'description': '',
                 'id': 'bdde3d818-fdcb-fg4b-de7f-6750dc8a9d7a',
                 'admin_state_up': True,
                 'subnet_id': 'bbe3d818-bdcb-4e4b-b47f-5650dc8a9d7a',
                 'tenant_id': 'a4eb9f4938bb418bbc4f8eb31802fefa',
                 'router_id': 'ade3d818-fdcb-fg4b-de7f-6750dc8a9d7a'},
                {'status': 'error',
                 'name': 'myvpn4',
                 'description': '',
                 'id': 'edde3d818-fdcb-fg4b-de7f-6750dc8a9d7a',
                 'admin_state_up': False,
                 'subnet_id': 'bbe3d818-bdcb-4e4b-b47f-5650dc8a9d7a',
                 'tenant_id': 'a4eb9f4938bb418bbc4f8eb31802fefa',
                 'router_id': 'ade3d818-fdcb-fg4b-de7f-6750dc8a9d7a'},
                {'status': 'UNKNOWN',
                 'name': 'myvpn5',
                 'description': '',
                 'id': '34e6383a-b1ab-4602-b26a-a1ae7b759212',
                 'admin_state_up': False,
                 'subnet_id': '8c20bbbf-1409-4bc4-b652-3aeda66746c1',
                 'tenant_id': 'a4eb9f4938bb418bbc4f8eb31802fefa',
                 'router_id': '0e5c9333-2ef5-4c90-9cca-5cc898515da4'},
                {'status': None,
                 'name': 'myvpn6',
                 'description': '',
                 'id': '6e94ff61-8dea-4154-98f1-4020e4b2cecd',
                 'admin_state_up': False,
                 'subnet_id': '5e2a20c3-547a-43e4-90c5-26d32ea42d10',
                 'tenant_id': 'a4eb9f4938bb418bbc4f8eb31802fefa',
                 'router_id': '5b14df87-60c1-4fc7-8ad5-7811b2199c7f'},
                ]

    def test_vpn_get_samples(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_vpn))
        self.assertEqual(len(self.fake_vpn), len(samples))
        self.assertEqual({vpn['id'] for vpn in self.fake_vpn},
                         {sample.resource_id for sample in samples})
        samples_dict = {sample.resource_id: sample for sample in samples}
        for vpn in self.fake_vpn:
            sample = samples_dict[vpn['id']]
            for field in self.pollster.FIELDS:
                self.assertEqual(vpn[field],
                                 sample.resource_metadata[field])

    def test_vpn_volume(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_vpn))
        self.assertEqual(1, samples[0].volume)
        self.assertEqual(0, samples[1].volume)
        self.assertEqual(2, samples[2].volume)
        self.assertEqual(7, samples[3].volume)
        self.assertEqual(-1, samples[4].volume)
        self.assertEqual(-1, samples[5].volume)

    def test_get_vpn_meter_names(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_vpn))
        self.assertEqual({'network.services.vpn'},
                         {s.name for s in samples})

    def test_vpn_discovery(self):
        discovered_vpns = discovery.VPNServicesDiscovery(
            self.CONF).discover(self.manager)
        self.assertEqual(len(self.fake_vpn), len(discovered_vpns))

        for vpn in self.fake_get_vpn_service():
            self.assertIn(vpn, discovered_vpns)


class TestIPSecConnectionsPollster(_BaseTestVPNPollster):

    def setUp(self):
        super().setUp()
        self.pollster = vpnaas.IPSecConnectionsPollster(self.CONF)
        fake_conns = self.fake_get_ipsec_connections()
        self.useFixture(fixtures.MockPatch('ceilometer.neutron_client.Client.'
                                           'ipsec_site_connections_get_all',
                                           return_value=fake_conns))

    @staticmethod
    def fake_get_ipsec_connections():
        return [{'name': 'connection1',
                 'description': 'Remote-connection1',
                 'peer_address': '192.168.1.10',
                 'peer_id': '192.168.1.10',
                 'peer_cidrs': ['192.168.2.0/24',
                                '192.168.3.0/24'],
                 'mtu': 1500,
                 'psk': 'abcd',
                 'initiator': 'bi-directional',
                 'dpd': {
                         'action': 'hold',
                         'interval': 30,
                         'timeout': 120},
                 'ikepolicy_id': 'ade3d818-fdcb-fg4b-de7f-4550dc8a9d7a',
                 'ipsecpolicy_id': 'fce3d818-fdcb-fg4b-de7f-7850dc8a9d7a',
                 'vpnservice_id': 'dce3d818-fdcb-fg4b-de7f-5650dc8a9d7a',
                 'admin_state_up': True,
                 'status': 'ACTIVE',
                 'tenant_id': 'abe3d818-fdcb-fg4b-de7f-6650dc8a9d7a',
                 'id': 'fdfbcec-fdcb-fg4b-de7f-6650dc8a9d7a'}
                ]

    def test_conns_get_samples(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_ipsec_connections()))
        self.assertEqual(1, len(samples))
        for field in self.pollster.FIELDS:
            self.assertEqual(self.fake_get_ipsec_connections()[0][field],
                             samples[0].resource_metadata[field])

    def test_get_conns_meter_names(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_ipsec_connections()))
        self.assertEqual({'network.services.vpn.connections'},
                         {s.name for s in samples})

    def test_conns_discovery(self):
        discovered_conns = discovery.IPSecConnectionsDiscovery(
            self.CONF).discover(self.manager)
        self.assertEqual(1, len(discovered_conns))
        self.assertEqual(self.fake_get_ipsec_connections(), discovered_conns)
