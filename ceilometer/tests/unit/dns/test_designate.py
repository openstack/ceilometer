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

from ceilometer.dns import designate
from ceilometer.dns import discovery
from ceilometer.polling import manager
from ceilometer import service
from ceilometer.tests import base
from ceilometer.tests.unit import fakes


class _BaseTestDNSPollster(base.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.addCleanup(mock.patch.stopall)
        self.CONF = service.prepare_service([], [])
        self.manager = manager.AgentManager(0, self.CONF)


class TestZoneStatusPollster(_BaseTestDNSPollster):

    def setUp(self):
        super().setUp()
        self.pollster = designate.ZoneStatusPollster(self.CONF)

    def test_zone_get_samples(self):
        resources = fakes.FakeSDKDesignateClient.default_zones

        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=resources))

        self.assertEqual(len(resources), len(samples))
        for field in self.pollster.FIELDS:
            self.assertEqual(
                getattr(resources[0], field),
                samples[0].resource_metadata[field])

    def test_zone_status_volume(self):
        resources = fakes.FakeSDKDesignateClient.default_zones

        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=resources))

        # ACTIVE = 1, PENDING = 2, ERROR = 3
        self.assertEqual(1, samples[0].volume)
        self.assertEqual(2, samples[1].volume)
        self.assertEqual(3, samples[2].volume)

    def test_get_zone_meter_names(self):
        resources = fakes.FakeSDKDesignateClient.default_zones

        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=resources))
        self.assertEqual({'dns.zone.status'},
                         {s.name for s in samples})

    def test_zone_discovery(self):
        discovered_zones = discovery.ZoneDiscovery(
            self.CONF).discover(self.manager)
        self.assertEqual(len(fakes.FakeSDKDesignateClient.default_zones),
                         len(list(discovered_zones)))


class TestZoneRecordsetCountPollster(_BaseTestDNSPollster):

    def setUp(self):
        super().setUp()
        self.pollster = designate.ZoneRecordsetCountPollster(self.CONF)

    def test_zone_recordsets_volume(self):
        resources = fakes.FakeSDKDesignateClient.default_zones
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=resources))

        # Each zone should have the mocked number of recordsets
        num_recordsets = len(fakes.FakeSDKDesignateClient.default_recordsets)
        for sample in samples:
            self.assertEqual(num_recordsets, sample.volume)

    def test_get_zone_meter_names(self):
        resources = fakes.FakeSDKDesignateClient.default_zones
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=resources))
        self.assertEqual({'dns.zone.recordsets'},
                         {s.name for s in samples})


class TestZoneTTLPollster(_BaseTestDNSPollster):

    def setUp(self):
        super().setUp()
        self.pollster = designate.ZoneTTLPollster(self.CONF)

    def test_zone_ttl_volume(self):
        resources = fakes.FakeSDKDesignateClient.default_zones

        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=resources))
        self.assertEqual(3600, samples[0].volume)
        self.assertEqual(7200, samples[1].volume)
        self.assertEqual(1800, samples[2].volume)

    def test_get_zone_meter_names(self):
        resources = fakes.FakeSDKDesignateClient.default_zones
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=resources))
        self.assertEqual({'dns.zone.ttl'},
                         {s.name for s in samples})


class TestZoneSerialPollster(_BaseTestDNSPollster):

    def setUp(self):
        super().setUp()
        self.pollster = designate.ZoneSerialPollster(self.CONF)

    def test_zone_serial_volume(self):
        resources = fakes.FakeSDKDesignateClient.default_zones
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=resources))
        self.assertEqual(1234567890, samples[0].volume)
        self.assertEqual(1234567891, samples[1].volume)
        self.assertEqual(1234567892, samples[2].volume)

    def test_get_zone_meter_names(self):
        resources = fakes.FakeSDKDesignateClient.default_zones
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=resources))
        self.assertEqual({'dns.zone.serial'},
                         {s.name for s in samples})


class TestZonePollsterUnknownStatus(_BaseTestDNSPollster):

    def test_unknown_zone_status(self):
        pollster = designate.ZoneStatusPollster(self.CONF)

        samples = list(pollster.get_samples(
            self.manager, {}, resources=[fakes.ZONE_UNKNOWN_STATUS]))
        self.assertEqual(1, len(samples))
        self.assertEqual(-1, samples[0].volume)
