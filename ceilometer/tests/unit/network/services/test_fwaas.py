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

import fixtures
import mock
from oslotest import base

from ceilometer.agent import manager
from ceilometer.agent import plugin_base
from ceilometer.network.services import discovery
from ceilometer.network.services import fwaas
from ceilometer import service


class _BaseTestFWPollster(base.BaseTestCase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(_BaseTestFWPollster, self).setUp()
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
        super(TestFirewallPollster, self).setUp()
        self.pollster = fwaas.FirewallPollster(self.CONF)
        fake_fw = self.fake_get_fw_service()
        self.useFixture(fixtures.MockPatch('ceilometer.neutron_client.Client.'
                                           'firewall_get_all',
                                           return_value=fake_fw))

    @staticmethod
    def fake_get_fw_service():
        return [{'status': 'ACTIVE',
                 'name': 'myfw',
                 'description': '',
                 'admin_state_up': True,
                 'id': 'fdde3d818-fdcb-fg4b-de7f-6750dc8a9d7a',
                 'firewall_policy_id': 'bbe3d818-bdcb-4e4b-b47f-5650dc8a9d7a',
                 'tenant_id': 'a4eb9f4938bb418bbc4f8eb31802fefa'},
                {'status': 'INACTIVE',
                 'name': 'myfw',
                 'description': '',
                 'admin_state_up': True,
                 'id': 'fdde3d818-fdcb-fg4b-de7f-6750dc8a9d7a',
                 'firewall_policy_id': 'bbe3d818-bdcb-4e4b-b47f-5650dc8a9d7a',
                 'tenant_id': 'a4eb9f4938bb418bbc4f8eb31802fefa'},
                {'status': 'PENDING_CREATE',
                 'name': 'myfw',
                 'description': '',
                 'admin_state_up': True,
                 'id': 'fdde3d818-fdcb-fg4b-de7f-6750dc8a9d7a',
                 'firewall_policy_id': 'bbe3d818-bdcb-4e4b-b47f-5650dc8a9d7a',
                 'tenant_id': 'a4eb9f4938bb418bbc4f8eb31802fefa'},
                {'status': 'error',
                 'name': 'myfw',
                 'description': '',
                 'admin_state_up': True,
                 'id': 'fdde3d818-fdcb-fg4b-de7f-6750dc8a9d7a',
                 'firewall_policy_id': 'bbe3d818-bdcb-4e4b-b47f-5650dc8a9d7a',
                 'tenant_id': 'a4eb9f4938bb418bbc4f8eb31802fefa'},
                ]

    def test_fw_get_samples(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_fw_service()))
        self.assertEqual(4, len(samples))
        for field in self.pollster.FIELDS:
            self.assertEqual(self.fake_get_fw_service()[0][field],
                             samples[0].resource_metadata[field])

    def test_vpn_volume(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_fw_service()))
        self.assertEqual(1, samples[0].volume)
        self.assertEqual(0, samples[1].volume)
        self.assertEqual(2, samples[2].volume)

    def test_get_vpn_meter_names(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_fw_service()))
        self.assertEqual(set(['network.services.firewall']),
                         set([s.name for s in samples]))

    def test_vpn_discovery(self):
        discovered_fws = discovery.FirewallDiscovery(
            self.CONF).discover(self.manager)
        self.assertEqual(3, len(discovered_fws))

        for vpn in self.fake_get_fw_service():
            if vpn['status'] == 'error':
                self.assertNotIn(vpn, discovered_fws)
            else:
                self.assertIn(vpn, discovered_fws)


class TestIPSecConnectionsPollster(_BaseTestFWPollster):

    def setUp(self):
        super(TestIPSecConnectionsPollster, self).setUp()
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
        self.assertEqual(set(['network.services.firewall.policy']),
                         set([s.name for s in samples]))

    def test_fw_policy_discovery(self):
        discovered_policy = discovery.FirewallPolicyDiscovery(
            self.CONF).discover(self.manager)
        self.assertEqual(1, len(discovered_policy))
        self.assertEqual(self.fake_get_fw_policy(), discovered_policy)
