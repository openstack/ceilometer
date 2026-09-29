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

import fixtures
from openstack import exceptions as os_exceptions
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
        self.conf.config(group='service_types', cinder='block-storage')

        self.mock_get_session = self.useFixture(fixtures.MockPatch(
            'ceilometer.keystone_client.get_session'))

        self.client = cinder_client.Client(self.CONF)

    def test_init_creates_connection_with_session(self):
        self.fake_conn_class_mock.assert_called_once_with(
            block_storage_api_version='3.64',
            session=self.mock_get_session.mock.return_value,
            oslo_conf=self.CONF,
            region_name='RegionOne',
            block_storage_interface='publicURL',
            service_types={'block-storage'})

    def test_list_volumes_returns_volumes(self):
        result = self.client.list_volumes(search_opts={'all_projects': True})

        self.assertEqual(fakes.VOLUME_LIST, result)

    def test_list_volumes_passes_search_opts(self):
        self.client.list_volumes(search_opts={'all_projects': False})

        self.fake_conn.block_storage.volumes.assert_called_once_with(
            details=True, all_projects=False)

    def test_list_volumes_default_opts(self):
        self.client.list_volumes()

        self.fake_conn.block_storage.volumes.assert_called_once_with(
            details=True, all_projects=True)

    def test_list_volumes_propagates_exception(self):
        self.fake_conn.block_storage.volumes = mock.Mock(
            side_effect=os_exceptions.HttpException())

        self.assertRaises(
            os_exceptions.HttpException,
            self.client.list_volumes)

    def test_list_volume_snapshots_returns_snapshots(self):
        result = self.client.list_volume_snapshots(
            search_opts={'all_projects': True})

        self.assertEqual(fakes.SNAPSHOT_LIST, result)

    def test_list_volume_snapshots_passes_search_opts(self):
        self.client.list_volume_snapshots(search_opts={'all_projects': False})

        self.fake_conn.block_storage.snapshots.assert_called_once_with(
            details=True, all_projects=False)

    def test_list_volume_snapshots_default_opts(self):
        self.client.list_volume_snapshots()

        self.fake_conn.block_storage.snapshots.assert_called_once_with(
            details=True, all_projects=True)

    def test_list_volume_snapshots_propagates_exception(self):
        self.fake_conn.block_storage.snapshots = mock.Mock(
            side_effect=os_exceptions.HttpException())

        self.assertRaises(
            os_exceptions.HttpException,
            self.client.list_volume_snapshots)

    def test_list_backups_returns_backups(self):
        result = self.client.list_backups(search_opts={'all_projects': True})

        self.assertEqual(fakes.BACKUP_LIST, result)

    def test_list_backups_passes_search_opts(self):
        self.client.list_backups(search_opts={'all_projects': False})

        self.fake_conn.block_storage.backups.assert_called_once_with(
            details=True, all_projects=False)

    def test_list_backups_default_opts(self):
        self.client.list_backups()

        self.fake_conn.block_storage.backups.assert_called_once_with(
            details=True, all_projects=True)

    def test_list_backups_propagates_exception(self):
        self.fake_conn.block_storage.backups = mock.Mock(
            side_effect=os_exceptions.HttpException())

        self.assertRaises(
            os_exceptions.HttpException,
            self.client.list_backups)

    def test_list_pools_returns_pools(self):
        result = self.client.list_pools()

        self.assertEqual(fakes.POOL_LIST, result)

    def test_list_pools_calls_backend_pools(self):
        self.client.list_pools()

        self.fake_conn.block_storage.backend_pools.assert_called_once_with()

    def test_list_pools_propagates_exception(self):
        self.fake_conn.block_storage.backend_pools = mock.Mock(
            side_effect=os_exceptions.HttpException())

        self.assertRaises(
            os_exceptions.HttpException,
            self.client.list_pools)

    def test_list_services(self):
        result = self.client.list_services()

        self.assertIsInstance(result, list)
        self.assertEqual(fakes.SERVICE_LIST, result)

    def test_list_services_calls_services(self):
        self.client.list_services()

        self.fake_conn.block_storage.services.assert_called_once_with()

    def test_list_services_propagates_exception(self):
        self.fake_conn.block_storage.services = mock.Mock(
            side_effect=os_exceptions.HttpException())

        self.assertRaises(
            os_exceptions.HttpException,
            self.client.list_services)
