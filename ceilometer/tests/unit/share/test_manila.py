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
from openstack.shared_file_system.v2 import share
from oslotest import base

from ceilometer.polling import manager
from ceilometer.polling import plugin_base
from ceilometer import service
from ceilometer.share import discovery
from ceilometer.share import manila


class _BaseTestSharePollster(base.BaseTestCase):

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
            return_value={'sharev2': mock.ANY})

    @staticmethod
    def fake_get_shares():
        return [
            share.Share(
                connection=None,
                id='share-1-uuid',
                name='my-share-1',
                availability_zone='az-1',
                share_protocol='NFS',
                share_type='default',
                share_network_id='network-1-uuid',
                status='available',
                host='host-1',
                is_public=False,
                size=100,
                project_id='tenant-1-uuid',
            ),
            share.Share(
                connection=None,
                id='share-2-uuid',
                name='my-share-2',
                availability_zone='az-2',
                share_protocol='CIFS',
                share_type='default',
                share_network_id='network-2-uuid',
                status='creating',
                host='host-2',
                is_public=True,
                size=50,
                project_id='tenant-2-uuid',
            ),
            share.Share(
                connection=None,
                id='share-3-uuid',
                name='my-share-3',
                availability_zone=None,
                share_protocol='NFS',
                share_type='default',
                share_network_id='network-3-uuid',
                status='error',
                host='host-3',
                is_public=False,
                size=200,
                project_id='tenant-1-uuid',
            ),
        ]


class TestShareStatusPollster(_BaseTestSharePollster):

    def setUp(self):
        super().setUp()
        self.pollster = manila.ShareStatusPollster(self.CONF)
        fake_shares = self.fake_get_shares()
        self.useFixture(fixtures.MockPatch(
            'ceilometer.manila_client.Client.shares_list',
            return_value=fake_shares))

    def test_share_get_samples(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_shares()))

        self.assertEqual(len(self.fake_get_shares()), len(samples))
        # Verify metadata fields are correctly extracted
        self.assertEqual('my-share-1', samples[0].resource_metadata['name'])
        self.assertEqual('az-1',
                         samples[0].resource_metadata['availability_zone'])
        # Verify share_protocol is renamed to protocol
        self.assertEqual('NFS', samples[0].resource_metadata['protocol'])
        self.assertNotIn('share_protocol', samples[0].resource_metadata)

    def test_share_status_volume(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_shares()))

        # available = 1, creating = 2, error = 4
        self.assertEqual(1, samples[0].volume)
        self.assertEqual(2, samples[1].volume)
        self.assertEqual(4, samples[2].volume)

    def test_get_share_meter_names(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_shares()))
        self.assertEqual({'manila.share.status'},
                         {s.name for s in samples})

    def test_share_discovery(self):
        with mock.patch('openstack.connection.Connection'):
            discovered_shares = discovery.ShareDiscovery(
                self.CONF).discover(self.manager)
        self.assertEqual(len(self.fake_get_shares()),
                         len(list(discovered_shares)))


class TestShareSizePollster(_BaseTestSharePollster):

    def setUp(self):
        super().setUp()
        self.pollster = manila.ShareSizePollster(self.CONF)

    def test_share_size_volume(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_shares()))
        self.assertEqual(100, samples[0].volume)
        self.assertEqual(50, samples[1].volume)
        self.assertEqual(200, samples[2].volume)

    def test_get_share_meter_names(self):
        samples = list(self.pollster.get_samples(
            self.manager, {},
            resources=self.fake_get_shares()))
        self.assertEqual({'manila.share.size'},
                         {s.name for s in samples})


class TestSharePollsterUnknownStatus(_BaseTestSharePollster):

    def test_unknown_share_status(self):
        pollster = manila.ShareStatusPollster(self.CONF)
        fake_share = share.Share(
            connection=None,
            id='share-unknown-uuid',
            name='my-share-unknown',
            availability_zone=None,
            share_protocol='NFS',
            share_type='default',
            share_network_id='network-unknown-uuid',
            status='UNKNOWN_STATUS',
            host='host-unknown',
            is_public=False,
            size=100,
            project_id='tenant-1-uuid',
        )
        samples = list(pollster.get_samples(
            self.manager, {}, resources=[fake_share]))
        self.assertEqual(1, len(samples))
        self.assertEqual(-1, samples[0].volume)
