# Copyright (C) 2026 Red Hat
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

from cinderclient import exceptions as cinder_exceptions
import fixtures
from oslo_config import fixture as config_fixture

from ceilometer import cinder_client
from ceilometer import service
from ceilometer.tests import base
from ceilometer.tests.unit import fakes


class TestCinderClient(base.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.CONF = service.prepare_service([], [])
        self.conf = self.useFixture(config_fixture.Config(self.CONF))
        self.conf.config(
            group='service_credentials',
            region_name='RegionOne',
            interface='publicURL')
        self.conf.config(group='service_types', cinder='volumev3')

        self.cinder_client = fakes.FakeCinderClient()
        self.mock_cinder_cls = self.useFixture(fixtures.MockPatch(
            'cinderclient.client.Client', return_value=self.cinder_client))
        self.mock_get_session = self.useFixture(fixtures.MockPatch(
            'ceilometer.keystone_client.get_session'))

        self.client = cinder_client.Client(self.CONF)

    def test_init_creates_cinderclient_with_session(self):
        self.mock_cinder_cls.mock.assert_called_once_with(
            version='3.64',
            session=self.mock_get_session.mock.return_value,
            region_name='RegionOne',
            interface='publicURL',
            service_type='volumev3')

    def test_list_volumes_returns_volumes(self):
        result = self.client.list_volumes(search_opts={'all_tenants': True})

        self.assertEqual(fakes.VOLUME_LIST, result)

    def test_list_volumes_passes_search_opts(self):
        with mock.patch.object(
                self.cinder_client.volumes, 'list',
                wraps=self.cinder_client.volumes.list) as spy:
            self.client.list_volumes(search_opts={'all_tenants': True})

        spy.assert_called_once_with(search_opts={'all_tenants': True})

    def test_list_volumes_default_opts(self):
        with mock.patch.object(
                self.cinder_client.volumes, 'list',
                wraps=self.cinder_client.volumes.list) as spy:
            self.client.list_volumes()

        spy.assert_called_once_with(search_opts={})

    def test_list_volumes_propagates_exception(self):
        self.cinder_client.volumes.list = mock.Mock(
            side_effect=cinder_exceptions.ClientException(
                500, 'Internal Server Error'))

        self.assertRaises(
            cinder_exceptions.ClientException,
            self.client.list_volumes)

    def test_list_volume_snapshots_returns_snapshots(self):
        result = self.client.list_volume_snapshots(
            search_opts={'all_tenants': True})

        self.assertEqual(fakes.SNAPSHOT_LIST, result)

    def test_list_volume_snapshots_passes_search_opts(self):
        with mock.patch.object(
                self.cinder_client.volume_snapshots, 'list',
                wraps=self.cinder_client.volume_snapshots.list) as spy:
            self.client.list_volume_snapshots(
                search_opts={'all_tenants': True})

        spy.assert_called_once_with(search_opts={'all_tenants': True})

    def test_list_volume_snapshots_propagates_exception(self):
        self.cinder_client.volume_snapshots.list = mock.Mock(
            side_effect=cinder_exceptions.ClientException(
                500, 'Internal Server Error'))

        self.assertRaises(
            cinder_exceptions.ClientException,
            self.client.list_volume_snapshots)

    def test_list_backups_returns_backups(self):
        result = self.client.list_backups(search_opts={'all_tenants': True})

        self.assertEqual(fakes.BACKUP_LIST, result)

    def test_list_backups_passes_search_opts(self):
        with mock.patch.object(
                self.cinder_client.backups, 'list',
                wraps=self.cinder_client.backups.list) as spy:
            self.client.list_backups(search_opts={'all_tenants': True})

        spy.assert_called_once_with(search_opts={'all_tenants': True})

    def test_list_backups_propagates_exception(self):
        self.cinder_client.backups.list = mock.Mock(
            side_effect=cinder_exceptions.ClientException(
                500, 'Internal Server Error'))

        self.assertRaises(
            cinder_exceptions.ClientException,
            self.client.list_backups)

    def test_list_pools_returns_pools(self):
        result = self.client.list_pools(detailed=True)

        self.assertEqual(fakes.POOL_LIST, result)

    def test_list_pools_passes_detailed(self):
        with mock.patch.object(
                self.cinder_client.pools, 'list',
                wraps=self.cinder_client.pools.list) as spy:
            self.client.list_pools(detailed=True)

        spy.assert_called_once_with(detailed=True)

    def test_list_pools_default_not_detailed(self):
        with mock.patch.object(
                self.cinder_client.pools, 'list',
                wraps=self.cinder_client.pools.list) as spy:
            self.client.list_pools()

        spy.assert_called_once_with(detailed=False)

    def test_list_pools_propagates_exception(self):
        self.cinder_client.pools.list = mock.Mock(
            side_effect=cinder_exceptions.ClientException(
                500, 'Internal Server Error'))

        self.assertRaises(
            cinder_exceptions.ClientException,
            self.client.list_pools)

    def test_list_services(self):
        result = self.client.list_services()

        self.assertIsInstance(result, list)
        self.assertEqual(fakes.SERVICE_LIST, result)

    def test_list_services_propagates_exception(self):
        self.cinder_client.services.list = mock.Mock(
            side_effect=cinder_exceptions.ClientException(
                500, 'Internal Server Error'))

        self.assertRaises(
            cinder_exceptions.ClientException,
            self.client.list_services)
