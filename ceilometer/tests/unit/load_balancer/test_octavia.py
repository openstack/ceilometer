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

from ceilometer.load_balancer import discovery
from ceilometer.load_balancer import octavia
from ceilometer.polling import manager
from ceilometer import service
from ceilometer.tests import base
from ceilometer.tests.unit import fakes


class _BaseTestLBPollster(base.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.CONF = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, self.CONF)


class TestLoadBalancerOperatingStatusPollster(_BaseTestLBPollster):

    def setUp(self):
        super().setUp()
        self.pollster = octavia.LoadBalancerOperatingStatusPollster(self.CONF)
        self.lbs = fakes.FakeSDKOctaviaClient.default_load_balancers

    def test_lb_get_samples(self):
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=self.lbs))
        self.assertEqual(len(self.lbs), len(samples))
        for field in self.pollster.FIELDS:
            self.assertEqual(
                getattr(self.lbs[0], field),
                samples[0].resource_metadata[field])

    def test_lb_operating_volume(self):
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=self.lbs))
        # ONLINE = 1, OFFLINE = 3, ERROR = 5, DEGRADED = 4
        self.assertEqual(1, samples[0].volume)
        self.assertEqual(3, samples[1].volume)
        self.assertEqual(5, samples[2].volume)
        self.assertEqual(4, samples[3].volume)

    def test_get_lb_meter_names(self):
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=self.lbs))
        self.assertEqual({'loadbalancer.operating'},
                         {s.name for s in samples})

    def test_lb_discovery(self):
        discovered_lbs = discovery.LoadBalancerDiscovery(
            self.CONF).discover(self.manager)
        expected = len(fakes.FakeSDKOctaviaClient.default_load_balancers)
        self.assertEqual(expected, len(list(discovered_lbs)))


class TestLoadBalancerProvisioningStatusPollster(_BaseTestLBPollster):

    def setUp(self):
        super().setUp()
        self.pollster = octavia.LoadBalancerProvisioningStatusPollster(
            self.CONF)
        self.lbs = fakes.FakeSDKOctaviaClient.default_load_balancers

    def test_lb_get_samples(self):
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=self.lbs))
        self.assertEqual(len(self.lbs), len(samples))
        for field in self.pollster.FIELDS:
            self.assertEqual(
                getattr(self.lbs[0], field),
                samples[0].resource_metadata[field])

    def test_lb_provisioning_volume(self):
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=self.lbs))
        # ACTIVE = 1, PENDING_UPDATE = 5, ERROR = 3, PENDING_DELETE = 6
        self.assertEqual(1, samples[0].volume)
        self.assertEqual(5, samples[1].volume)
        self.assertEqual(3, samples[2].volume)
        self.assertEqual(6, samples[3].volume)

    def test_get_lb_meter_names(self):
        samples = list(self.pollster.get_samples(
            self.manager, {}, resources=self.lbs))
        self.assertEqual({'loadbalancer.provisioning'},
                         {s.name for s in samples})


class TestLoadBalancerPollsterUnknownStatus(_BaseTestLBPollster):

    def test_unknown_operating_status(self):
        pollster = octavia.LoadBalancerOperatingStatusPollster(self.CONF)
        samples = list(pollster.get_samples(
            self.manager, {}, resources=[fakes.LB_UNKNOWN_OPERATING_STATUS]))
        self.assertEqual(1, len(samples))
        self.assertEqual(-1, samples[0].volume)

    def test_unknown_provisioning_status(self):
        pollster = octavia.LoadBalancerProvisioningStatusPollster(self.CONF)
        samples = list(pollster.get_samples(
            self.manager, {},
            resources=[fakes.LB_UNKNOWN_PROVISIONING_STATUS]))
        self.assertEqual(1, len(samples))
        self.assertEqual(-1, samples[0].volume)
