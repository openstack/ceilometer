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
from openstack.dns.v2 import recordset
from openstack.dns.v2 import zone
from oslotest import base

from ceilometer.dns import designate
from ceilometer.dns import discovery
from ceilometer.polling import manager
from ceilometer.polling import plugin_base
from ceilometer import service


class _BaseTestDNSPollster(base.BaseTestCase):

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
            return_value={'dns': mock.ANY})

    @staticmethod
    def fake_get_zones():
        return [
            zone.Zone(
                connection=None,
                id='zone-1-uuid',
                name='example.com.',
                email='admin@example.com',
                ttl=3600,
                description='Example zone',
                type='PRIMARY',
                status='ACTIVE',
                action='NONE',
                serial=1234567890,
                pool_id='pool-1',
                project_id='tenant-1-uuid',
            ),
            zone.Zone(
                connection=None,
                id='zone-2-uuid',
                name='test.org.',
                email='admin@test.org',
                ttl=7200,
                description='Test zone',
                type='PRIMARY',
                status='PENDING',
                action='CREATE',
                serial=1234567891,
                pool_id='pool-1',
                project_id='tenant-2-uuid',
            ),
            zone.Zone(
                connection=None,
                id='zone-3-uuid',
                name='error.net.',
                email='admin@error.net',
                ttl=1800,
                description='Error zone',
                type='PRIMARY',
                status='ERROR',
                action='UPDATE',
                serial=1234567892,
                pool_id='pool-2',
                project_id='tenant-1-uuid',
            ),
        ]

    @staticmethod
    def fake_get_recordsets():
        return [
            recordset.Recordset(
                connection=None,
                id='rs-1-uuid',
                name='www.example.com.',
                type='A',
                records=['192.168.1.1'],
                ttl=3600,
            ),
            recordset.Recordset(
                connection=None,
                id='rs-2-uuid',
                name='mail.example.com.',
                type='MX',
                records=['10 mail.example.com.'],
                ttl=3600,
            ),
        ]


class TestZoneStatusPollster(_BaseTestDNSPollster):

    def setUp(self):
        super().setUp()
        self.pollster = designate.ZoneStatusPollster(self.CONF)
        fake_zones = self.fake_get_zones()
        self.useFixture(fixtures.MockPatch(
            'ceilometer.designate_client.Client.zones_list',
            return_value=fake_zones))

    def test_zone_get_samples(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_zones()))

        self.assertEqual(len(self.fake_get_zones()), len(samples))
        for field in self.pollster.FIELDS:
            self.assertEqual(
                getattr(self.fake_get_zones()[0], field),
                samples[0].resource_metadata[field])

    def test_zone_status_volume(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_zones()))

        # ACTIVE = 1, PENDING = 2, ERROR = 3
        self.assertEqual(1, samples[0].volume)
        self.assertEqual(2, samples[1].volume)
        self.assertEqual(3, samples[2].volume)

    def test_get_zone_meter_names(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_zones()))
        self.assertEqual({'dns.zone.status'},
                         {s.name for s in samples})

    def test_zone_discovery(self):
        with mock.patch('openstack.connection.Connection'):
            discovered_zones = discovery.ZoneDiscovery(
                self.CONF).discover(self.manager)
        self.assertEqual(len(self.fake_get_zones()),
                         len(list(discovered_zones)))


class TestZoneRecordsetCountPollster(_BaseTestDNSPollster):

    def setUp(self):
        super().setUp()
        with mock.patch('openstack.connection.Connection'):
            self.pollster = designate.ZoneRecordsetCountPollster(self.CONF)
        self.useFixture(fixtures.MockPatch(
            'ceilometer.designate_client.Client.recordsets_list',
            return_value=self.fake_get_recordsets()))

    def test_zone_recordsets_volume(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_zones()))

        # Each zone should have the mocked number of recordsets
        num_recordsets = len(self.fake_get_recordsets())
        for sample in samples:
            self.assertEqual(num_recordsets, sample.volume)

    def test_get_zone_meter_names(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_zones()))
        self.assertEqual({'dns.zone.recordsets'},
                         {s.name for s in samples})


class TestZoneTTLPollster(_BaseTestDNSPollster):

    def setUp(self):
        super().setUp()
        self.pollster = designate.ZoneTTLPollster(self.CONF)

    def test_zone_ttl_volume(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_zones()))
        self.assertEqual(3600, samples[0].volume)
        self.assertEqual(7200, samples[1].volume)
        self.assertEqual(1800, samples[2].volume)

    def test_get_zone_meter_names(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_zones()))
        self.assertEqual({'dns.zone.ttl'},
                         {s.name for s in samples})


class TestZoneSerialPollster(_BaseTestDNSPollster):

    def setUp(self):
        super().setUp()
        self.pollster = designate.ZoneSerialPollster(self.CONF)

    def test_zone_serial_volume(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_zones()))
        self.assertEqual(1234567890, samples[0].volume)
        self.assertEqual(1234567891, samples[1].volume)
        self.assertEqual(1234567892, samples[2].volume)

    def test_get_zone_meter_names(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_zones()))
        self.assertEqual({'dns.zone.serial'},
                         {s.name for s in samples})


class TestZonePollsterUnknownStatus(_BaseTestDNSPollster):

    def test_unknown_zone_status(self):
        pollster = designate.ZoneStatusPollster(self.CONF)
        fake_zone = zone.Zone(
            connection=None,
            id='zone-unknown-uuid',
            name='unknown.com.',
            email='admin@unknown.com',
            ttl=3600,
            description='Unknown zone',
            type='PRIMARY',
            status='UNKNOWN_STATUS',
            action='NONE',
            serial=1234567893,
            pool_id='pool-1',
            project_id='tenant-1-uuid',
        )
        samples = list(pollster.get_samples(
            self.manager, {}, resources=[fake_zone]))
        self.assertEqual(1, len(samples))
        self.assertEqual(-1, samples[0].volume)
