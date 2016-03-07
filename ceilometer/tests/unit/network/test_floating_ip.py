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

import mock
from oslotest import base
from oslotest import mockpatch

from ceilometer.agent import manager
from ceilometer.agent import plugin_base
from ceilometer.network import floatingip


class _BaseTestFloatingIPPollster(base.BaseTestCase):

    @mock.patch('ceilometer.pipeline.setup_pipeline', mock.MagicMock())
    def setUp(self):
        super(_BaseTestFloatingIPPollster, self).setUp()
        self.manager = manager.AgentManager()
        plugin_base._get_keystone = mock.Mock()


class TestFloatingIPPollster(_BaseTestFloatingIPPollster):

    def setUp(self):
        super(TestFloatingIPPollster, self).setUp()
        self.pollster = floatingip.FloatingIPPollster()
        fake_fip = self.fake_get_fip_service()
        self.useFixture(mockpatch.Patch('ceilometer.neutron_client.Client.'
                                        'fip_get_all',
                                        return_value=fake_fip))

    @staticmethod
    def fake_get_fip_service():
        return [{'router_id': 'e24f8a37-1bb7-49e4-833c-049bb21986d2',
                 'status':  'ACTIVE',
                 'tenant_id': '54a00c50ee4c4396b2f8dc220a2bed57',
                 'floating_network_id':
                     'f41f399e-d63e-47c6-9a19-21c4e4fbbba0',
                 'fixed_ip_address': '10.0.0.6',
                 'floating_ip_address': '65.79.162.11',
                 'port_id': '93a0d2c7-a397-444c-9d75-d2ac89b6f209',
                 'id': '18ca27bf-72bc-40c8-9c13-414d564ea367'},
                {'router_id': 'astf8a37-1bb7-49e4-833c-049bb21986d2',
                 'status':  'DOWN',
                 'tenant_id': '34a00c50ee4c4396b2f8dc220a2bed57',
                 'floating_network_id':
                     'gh1f399e-d63e-47c6-9a19-21c4e4fbbba0',
                 'fixed_ip_address': '10.0.0.7',
                 'floating_ip_address': '65.79.162.12',
                 'port_id': '453a0d2c7-a397-444c-9d75-d2ac89b6f209',
                 'id': 'jkca27bf-72bc-40c8-9c13-414d564ea367'},
                {'router_id': 'e2478937-1bb7-49e4-833c-049bb21986d2',
                 'status':  'error',
                 'tenant_id': '54a0gggg50ee4c4396b2f8dc220a2bed57',
                 'floating_network_id':
                     'po1f399e-d63e-47c6-9a19-21c4e4fbbba0',
                 'fixed_ip_address': '10.0.0.8',
                 'floating_ip_address': '65.79.162.13',
                 'port_id': '67a0d2c7-a397-444c-9d75-d2ac89b6f209',
                 'id': '90ca27bf-72bc-40c8-9c13-414d564ea367'}]

    def test_default_discovery(self):
        self.assertEqual('endpoint:network', self.pollster.default_discovery)

    def test_fip_get_samples(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=['http://localhost:9696/']))
        self.assertEqual(1, len(samples))
        self.assertEqual('18ca27bf-72bc-40c8-9c13-414d564ea367',
                         samples[0].resource_id)
        self.assertEqual("65.79.162.11", samples[0].resource_metadata[
            "floating_ip_address"])
        self.assertEqual("10.0.0.6", samples[0].resource_metadata[
            "fixed_ip_address"])

    def test_fip_volume(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=['http://localhost:9696/']))
        self.assertEqual(1, samples[0].volume)

    def test_get_fip_meter_names(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=['http://localhost:9696/']))
        self.assertEqual(set(['ip.floating']),
                         set([s.name for s in samples]))
