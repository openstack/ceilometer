# Copyright 2016 Sungard Availability Services
# Copyright 2016 Red Hat
# All Rights Reserved
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
from unittest import mock

import fixtures
from oslotest import base

from ceilometer.network import floatingip
from ceilometer.network.services import discovery
from ceilometer.polling import manager
from ceilometer.polling import plugin_base
from ceilometer import service


class _BaseTestFloatingIPPollster(base.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.CONF = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, self.CONF)
        plugin_base._get_keystone = mock.Mock()


class TestFloatingIPPollster(_BaseTestFloatingIPPollster):

    def setUp(self):
        super().setUp()
        self.pollster = floatingip.FloatingIPPollster(self.CONF)
        self.fake_fip = self.fake_get_fip_service()
        self.useFixture(fixtures.MockPatch('ceilometer.neutron_client.Client.'
                                           'fip_get_all',
                                           return_value=self.fake_fip))

    @staticmethod
    def fake_get_fip_service():
        return [{'router_id': 'e24f8a37-1bb7-49e4-833c-049bb21986d2',
                 'status': 'ACTIVE',
                 'tenant_id': '54a00c50ee4c4396b2f8dc220a2bed57',
                 'floating_network_id':
                     'f41f399e-d63e-47c6-9a19-21c4e4fbbba0',
                 'fixed_ip_address': '10.0.0.6',
                 'floating_ip_address': '65.79.162.11',
                 'port_id': '93a0d2c7-a397-444c-9d75-d2ac89b6f209',
                 'id': '18ca27bf-72bc-40c8-9c13-414d564ea367'},
                {'router_id': 'astf8a37-1bb7-49e4-833c-049bb21986d2',
                 'status': 'DOWN',
                 'tenant_id': '34a00c50ee4c4396b2f8dc220a2bed57',
                 'floating_network_id':
                     'gh1f399e-d63e-47c6-9a19-21c4e4fbbba0',
                 'fixed_ip_address': '10.0.0.7',
                 'floating_ip_address': '65.79.162.12',
                 'port_id': '453a0d2c7-a397-444c-9d75-d2ac89b6f209',
                 'id': 'jkca27bf-72bc-40c8-9c13-414d564ea367'},
                {'router_id': 'e2478937-1bb7-49e4-833c-049bb21986d2',
                 'status': 'error',
                 'tenant_id': '54a0gggg50ee4c4396b2f8dc220a2bed57',
                 'floating_network_id':
                     'po1f399e-d63e-47c6-9a19-21c4e4fbbba0',
                 'fixed_ip_address': '10.0.0.8',
                 'floating_ip_address': '65.79.162.13',
                 'port_id': '67a0d2c7-a397-444c-9d75-d2ac89b6f209',
                 'id': '90ca27bf-72bc-40c8-9c13-414d564ea367'},
                {'router_id': 'a27ac630-939f-4e2e-bbc3-09a6b4f19a77',
                 'status': 'UNKNOWN',
                 'tenant_id': '54a0gggg50ee4c4396b2f8dc220a2bed57',
                 'floating_network_id':
                     '4d0c3f4f-79c7-40ff-9b0d-6e3a396547db',
                 'fixed_ip_address': '10.0.0.9',
                 'floating_ip_address': '65.79.162.14',
                 'port_id': '59cc6efa-7c89-4730-b051-b15f594e6728',
                 'id': 'a8a11884-7666-4f35-901e-dbb84e7111b5'},
                {'router_id': '7eb0adde-6c3b-4a77-9714-f718a17afb83',
                 'status': None,
                 'tenant_id': '54a0gggg50ee4c4396b2f8dc220a2bed57',
                 'floating_network_id':
                     'bd6290e6-b014-4cd3-91f0-7e8a1b4c26ab',
                 'fixed_ip_address': '10.0.0.10',
                 'floating_ip_address': '65.79.162.15',
                 'port_id': 'd3b9436d-4b2b-4832-852b-34df7513c935',
                 'id': '27c539ca-94ce-42fc-a639-1bf2c8690d76'}]

    def test_fip_get_samples(self):
        samples = list(self.pollster.get_samples(
                       self.manager, {},
                       resources=self.fake_fip))
        self.assertEqual(len(self.fake_fip), len(samples))
        self.assertEqual({fip['id'] for fip in self.fake_fip},
                         {sample.resource_id for sample in samples})
        samples_dict = {sample.resource_id: sample for sample in samples}
        for fip in self.fake_fip:
            sample = samples_dict[fip['id']]
            for field in self.pollster.FIELDS:
                self.assertEqual(fip[field],
                                 sample.resource_metadata[field])

    def test_fip_volume(self):
        samples = list(self.pollster.get_samples(
                       self.manager, {},
                       resources=self.fake_fip))
        self.assertEqual(1, samples[0].volume)
        self.assertEqual(3, samples[1].volume)
        self.assertEqual(7, samples[2].volume)
        self.assertEqual(-1, samples[3].volume)
        self.assertEqual(-1, samples[4].volume)

    def test_get_fip_meter_names(self):
        samples = list(self.pollster.get_samples(
                       self.manager, {},
                       resources=self.fake_fip))
        self.assertEqual({'ip.floating'},
                         {s.name for s in samples})

    def test_fip_discovery(self):
        discovered_fips = discovery.FloatingIPDiscovery(
            self.CONF).discover(self.manager)
        self.assertEqual(len(self.fake_fip), len(discovered_fips))
        for fip in self.fake_fip:
            self.assertIn(fip, discovered_fips)
