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

from ceilometer.load_balancer import discovery
from ceilometer.load_balancer import octavia
from ceilometer.polling import manager
from ceilometer.polling import plugin_base
from ceilometer import service


class FakeLoadBalancer:
    """Fake load balancer object mimicking openstacksdk Resource."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class _BaseTestLBPollster(base.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.addCleanup(mock.patch.stopall)
        self.CONF = service.prepare_service([], [])
        # Mock the openstack.connection.Connection to avoid auth issues
        with mock.patch('openstack.connection.Connection'):
            self.manager = manager.AgentManager(0, self.CONF)
        plugin_base._get_keystone = mock.Mock()
        catalog = (plugin_base._get_keystone.session.auth.get_access.
                   return_value.service_catalog)
        catalog.get_endpoints = mock.MagicMock(
            return_value={'load-balancer': mock.ANY})

    @staticmethod
    def fake_get_loadbalancers():
        return [
            FakeLoadBalancer(
                id='lb-1-uuid',
                name='my-lb-1',
                availability_zone='az-1',
                vip_address='192.168.1.10',
                vip_port_id='port-1-uuid',
                provisioning_status='ACTIVE',
                operating_status='ONLINE',
                provider='amphora',
                flavor_id='flavor-1',
                project_id='tenant-1-uuid',
            ),
            FakeLoadBalancer(
                id='lb-2-uuid',
                name='my-lb-2',
                availability_zone='az-2',
                vip_address='192.168.1.11',
                vip_port_id='port-2-uuid',
                provisioning_status='PENDING_UPDATE',
                operating_status='OFFLINE',
                provider='amphora',
                flavor_id='flavor-1',
                project_id='tenant-2-uuid',
            ),
            FakeLoadBalancer(
                id='lb-3-uuid',
                name='my-lb-3',
                availability_zone=None,
                vip_address='192.168.1.12',
                vip_port_id='port-3-uuid',
                provisioning_status='ERROR',
                operating_status='ERROR',
                provider='amphora',
                flavor_id='flavor-1',
                project_id='tenant-1-uuid',
            ),
            FakeLoadBalancer(
                id='lb-4-uuid',
                name='my-lb-4',
                availability_zone='az-1',
                vip_address='192.168.1.13',
                vip_port_id='port-4-uuid',
                provisioning_status='PENDING_DELETE',
                operating_status='DEGRADED',
                provider='amphora',
                flavor_id='flavor-1',
                project_id='tenant-1-uuid',
            ),
        ]


class TestLoadBalancerOperatingStatusPollster(_BaseTestLBPollster):

    def setUp(self):
        super().setUp()
        self.pollster = octavia.LoadBalancerOperatingStatusPollster(self.CONF)
        fake_lbs = self.fake_get_loadbalancers()
        self.useFixture(fixtures.MockPatch(
            'ceilometer.octavia_client.Client.loadbalancers_list',
            return_value=fake_lbs))

    def test_lb_get_samples(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_loadbalancers()))
        self.assertEqual(4, len(samples))
        for field in self.pollster.FIELDS:
            self.assertEqual(
                getattr(self.fake_get_loadbalancers()[0], field),
                samples[0].resource_metadata[field])

    def test_lb_operating_volume(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_loadbalancers()))
        # ONLINE = 1, OFFLINE = 3, ERROR = 5, DEGRADED = 4
        self.assertEqual(1, samples[0].volume)
        self.assertEqual(3, samples[1].volume)
        self.assertEqual(5, samples[2].volume)
        self.assertEqual(4, samples[3].volume)

    def test_get_lb_meter_names(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_loadbalancers()))
        self.assertEqual({'loadbalancer.operating'},
                         {s.name for s in samples})

    def test_lb_discovery(self):
        with mock.patch('openstack.connection.Connection'):
            discovered_lbs = discovery.LoadBalancerDiscovery(
                self.CONF).discover(self.manager)
        self.assertEqual(4, len(list(discovered_lbs)))


class TestLoadBalancerProvisioningStatusPollster(_BaseTestLBPollster):

    def setUp(self):
        super().setUp()
        self.pollster = octavia.LoadBalancerProvisioningStatusPollster(
            self.CONF)
        fake_lbs = self.fake_get_loadbalancers()
        self.useFixture(fixtures.MockPatch(
            'ceilometer.octavia_client.Client.loadbalancers_list',
            return_value=fake_lbs))

    def test_lb_get_samples(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_loadbalancers()))
        self.assertEqual(4, len(samples))
        for field in self.pollster.FIELDS:
            self.assertEqual(
                getattr(self.fake_get_loadbalancers()[0], field),
                samples[0].resource_metadata[field])

    def test_lb_provisioning_volume(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_loadbalancers()))
        # ACTIVE = 1, PENDING_UPDATE = 5, ERROR = 3, PENDING_DELETE = 6
        self.assertEqual(1, samples[0].volume)
        self.assertEqual(5, samples[1].volume)
        self.assertEqual(3, samples[2].volume)
        self.assertEqual(6, samples[3].volume)

    def test_get_lb_meter_names(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_loadbalancers()))
        self.assertEqual({'loadbalancer.provisioning'},
                         {s.name for s in samples})


class TestLoadBalancerPollsterUnknownStatus(_BaseTestLBPollster):

    def test_unknown_operating_status(self):
        pollster = octavia.LoadBalancerOperatingStatusPollster(self.CONF)
        fake_lb = FakeLoadBalancer(
            id='lb-unknown-uuid',
            name='my-lb-unknown',
            availability_zone=None,
            vip_address='192.168.1.99',
            vip_port_id='port-unknown-uuid',
            provisioning_status='ACTIVE',
            operating_status='UNKNOWN_STATUS',
            provider='amphora',
            flavor_id='flavor-1',
            project_id='tenant-1-uuid',
        )
        samples = list(pollster.get_samples(
            self.manager, {}, resources=[fake_lb]))
        self.assertEqual(1, len(samples))
        self.assertEqual(-1, samples[0].volume)

    def test_unknown_provisioning_status(self):
        pollster = octavia.LoadBalancerProvisioningStatusPollster(self.CONF)
        fake_lb = FakeLoadBalancer(
            id='lb-unknown-uuid',
            name='my-lb-unknown',
            availability_zone=None,
            vip_address='192.168.1.99',
            vip_port_id='port-unknown-uuid',
            provisioning_status='UNKNOWN_STATUS',
            operating_status='ONLINE',
            provider='amphora',
            flavor_id='flavor-1',
            project_id='tenant-1-uuid',
        )
        samples = list(pollster.get_samples(
            self.manager, {}, resources=[fake_lb]))
        self.assertEqual(1, len(samples))
        self.assertEqual(-1, samples[0].volume)
