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
from ceilometer.network.services import fwaas
from ceilometer.polling import manager
from ceilometer.polling import plugin_base
from ceilometer import service


class _BaseTestFWPollster(base.BaseTestCase):

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


class TestFirewallPollster(_BaseTestFWPollster):

    def setUp(self):
        super().setUp()
        self.pollster = fwaas.FirewallPollster(self.CONF)
        self.fake_fw = self.fake_get_fw_service()
        self.useFixture(fixtures.MockPatch('ceilometer.neutron_client.Client.'
                                           'firewall_get_all',
                                           return_value=self.fake_fw))

    @staticmethod
    def fake_get_fw_service():
        return [{'status': 'ACTIVE',
                 'name': 'myfw1',
                 'description': '',
                 'admin_state_up': True,
                 'id': 'fdde3d818-fdcb-fg4b-de7f-6750dc8a9d7a',
                 'firewall_policy_id': 'bbe3d818-bdcb-4e4b-b47f-5650dc8a9d7a',
                 'tenant_id': 'a4eb9f4938bb418bbc4f8eb31802fefa'},
                {'status': 'INACTIVE',
                 'name': 'myfw2',
                 'description': '',
                 'admin_state_up': True,
                 'id': 'e0d707dc-6194-4471-8286-0635bf65a055',
                 'firewall_policy_id': 'e0d707dc-6194-4471-8286-0635bf65a055',
                 'tenant_id': 'a4eb9f4938bb418bbc4f8eb31802fefa'},
                {'status': 'PENDING_CREATE',
                 'name': 'myfw3',
                 'description': '',
                 'admin_state_up': True,
                 'id': 'e538d353-31e9-4581-a511-0a487ff71d0d',
                 'firewall_policy_id': 'bbe3d818-bdcb-4e4b-b47f-5650dc8a9d7a',
                 'tenant_id': 'a4eb9f4938bb418bbc4f8eb31802fefa'},
                {'status': 'ERROR',
                 'name': 'myfw4',
                 'description': '',
                 'admin_state_up': True,
                 'id': '06f698c4-dc63-43c4-a2d9-7b978e80f09a',
                 'firewall_policy_id': 'bef98f97-789f-418e-82ad-3e5d69618916',
                 'tenant_id': 'a4eb9f4938bb418bbc4f8eb31802fefa'},
                {'status': 'UNKNOWN',
                 'name': 'myfw5',
                 'description': '',
                 'admin_state_up': True,
                 'id': 'c65a1bec-ab59-44ce-b784-1c725f427998',
                 'firewall_policy_id': 'd45b975e-738f-42c3-a4b3-760d3a58ab51',
                 'tenant_id': 'a4eb9f4938bb418bbc4f8eb31802fefa'},
                {'status': None,
                 'name': 'myfw6',
                 'description': '',
                 'admin_state_up': True,
                 'id': 'ab5d19ff-32a8-49e5-aa2b-d008157359d9',
                 'firewall_policy_id': '79b9c933-2a7c-4f93-bbf9-d165f0326581',
                 'tenant_id': 'a4eb9f4938bb418bbc4f8eb31802fefa'},
                ]

    def test_fw_get_samples(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_fw))
        self.assertEqual(len(self.fake_fw), len(samples))
        self.assertEqual({fw['id'] for fw in self.fake_fw},
                         {sample.resource_id for sample in samples})
        samples_dict = {sample.resource_id: sample for sample in samples}
        for fw in self.fake_fw:
            sample = samples_dict[fw['id']]
            for field in self.pollster.FIELDS:
                self.assertEqual(fw[field],
                                 sample.resource_metadata[field])

    def test_vpn_volume(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_fw))
        self.assertEqual(1, samples[0].volume)
        self.assertEqual(0, samples[1].volume)
        self.assertEqual(2, samples[2].volume)
        self.assertEqual(7, samples[3].volume)
        self.assertEqual(-1, samples[4].volume)
        self.assertEqual(-1, samples[5].volume)

    def test_get_vpn_meter_names(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_fw))
        self.assertEqual({'network.services.firewall'},
                         {s.name for s in samples})

    def test_vpn_discovery(self):
        discovered_fws = discovery.FirewallDiscovery(
            self.CONF).discover(self.manager)
        self.assertEqual(len(self.fake_fw), len(discovered_fws))

        for vpn in self.fake_fw:
            self.assertIn(vpn, discovered_fws)


class TestIPSecConnectionsPollster(_BaseTestFWPollster):

    def setUp(self):
        super().setUp()
        self.pollster = fwaas.FirewallPolicyPollster(self.CONF)
        fake_fw_policy = self.fake_get_fw_policy()
        self.useFixture(fixtures.MockPatch('ceilometer.neutron_client.Client.'
                                           'fw_policy_get_all',
                                           return_value=fake_fw_policy))

    @staticmethod
    def fake_get_fw_policy():
        return [{'name': 'my_fw_policy',
                 'description': 'fw_policy',
                 'admin_state_up': True,
                 'tenant_id': 'abe3d818-fdcb-fg4b-de7f-6650dc8a9d7a',
                 'firewall_rules': [{'enabled': True,
                                     'action': 'allow',
                                     'ip_version': 4,
                                     'protocol': 'tcp',
                                     'destination_port': '80',
                                     'source_ip_address': '10.24.4.2'},
                                    {'enabled': True,
                                     'action': 'deny',
                                     'ip_version': 4,
                                     'protocol': 'tcp',
                                     'destination_port': '22'}],
                 'shared': True,
                 'audited': True,
                 'id': 'fdfbcec-fdcb-fg4b-de7f-6650dc8a9d7a'}
                ]

    def test_policy_get_samples(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_fw_policy()))
        self.assertEqual(1, len(samples))
        for field in self.pollster.FIELDS:
            self.assertEqual(self.fake_get_fw_policy()[0][field],
                             samples[0].resource_metadata[field])

    def test_get_policy_meter_names(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_fw_policy()))
        self.assertEqual({'network.services.firewall.policy'},
                         {s.name for s in samples})

    def test_fw_policy_discovery(self):
        discovered_policy = discovery.FirewallPolicyDiscovery(
            self.CONF).discover(self.manager)
        self.assertEqual(1, len(discovered_policy))
        self.assertEqual(self.fake_get_fw_policy(), discovered_policy)
