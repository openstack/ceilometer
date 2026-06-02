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

from ceilometer import service
from ceilometer.tests import base
from ceilometer.tests.unit import fakes
from ceilometer.volume import discovery


class _BaseDiscoveryTestCase(base.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.CONF = service.prepare_service([], [])
        self.useFixture(
            fixtures.MockPatch('ceilometer.keystone_client.get_session'))
        self.useFixture(fixtures.MockPatch(
            'cinderclient.client.Client',
            return_value=fakes.FakeCinderClient()))
        self.manager = mock.Mock()

    def cinder_client_exception(self, *args, **kwargs):
        """Raises a cinder ClientException for use in tests as a side effect.

        """

        raise cinder_exceptions.ClientException(500)


class TestVolumeDiscovery(_BaseDiscoveryTestCase):

    def setUp(self):
        super().setUp()
        self.discovery = discovery.VolumeDiscovery(self.CONF)

    def test_discover_returns_volumes(self):
        resources = self.discovery.discover(self.manager)

        self.assertEqual(fakes.VOLUME_LIST, resources)

    def test_discover_empty(self):
        self.discovery.client.volumes.list = mock.Mock(
            return_value=[])

        resources = self.discovery.discover(self.manager)

        self.assertEqual([], resources)

    def test_discover_calls_list_volumes_with_all_tenants(self):
        with mock.patch.object(
            self.discovery.client.volumes, 'list',
            wraps=self.discovery.client.volumes.list
        ) as spy:

            self.discovery.discover(self.manager)

            spy.assert_called_once_with(search_opts={'all_tenants': True})

    def test_discover_propagates_exception(self):
        self.discovery.client.volumes.list = (
            self.cinder_client_exception)

        self.assertRaises(
            cinder_exceptions.ClientException,
            self.discovery.discover, self.manager)


class TestVolumeSnapshotsDiscovery(_BaseDiscoveryTestCase):

    def setUp(self):
        super().setUp()
        self.discovery = discovery.VolumeSnapshotsDiscovery(self.CONF)

    def test_discover_returns_snapshots(self):
        resources = self.discovery.discover(self.manager)

        self.assertEqual(fakes.SNAPSHOT_LIST, resources)

    def test_discover_empty(self):
        self.discovery.client.volume_snapshots.list = mock.Mock(
            return_value=[])

        resources = self.discovery.discover(self.manager)

        self.assertEqual([], resources)

    def test_discover_calls_list_snapshots_with_all_tenants(self):
        with mock.patch.object(
            self.discovery.client.volume_snapshots, 'list',
            wraps=self.discovery.client.volume_snapshots.list
        ) as spy:
            self.discovery.discover(self.manager)

            spy.assert_called_once_with(search_opts={'all_tenants': True})

    def test_discover_propagates_exception(self):
        with mock.patch.object(
                self.discovery.client.volume_snapshots, 'list',
                side_effect=cinder_exceptions.ClientException(500)):

            self.discovery = discovery.VolumeSnapshotsDiscovery(self.CONF)

            self.assertRaises(
                cinder_exceptions.ClientException,
                self.discovery.discover, self.manager)


class TestVolumeBackupsDiscovery(_BaseDiscoveryTestCase):

    def setUp(self):
        super().setUp()
        self.discovery = discovery.VolumeBackupsDiscovery(self.CONF)

    def test_discover_returns_backups(self):
        resources = self.discovery.discover(self.manager)

        self.assertEqual(fakes.BACKUP_LIST, resources)

    def test_discover_empty(self):
        self.discovery.client.backups.list = mock.Mock(return_value=[])

        resources = self.discovery.discover(self.manager)

        self.assertEqual([], resources)

    def test_discover_calls_list_backups_with_all_tenants(self):
        with mock.patch.object(
                self.discovery.client.backups, 'list',
                wraps=self.discovery.client.backups.list) as spy:

            self.discovery.discover(self.manager)

            spy.assert_called_once_with(
                search_opts={'all_tenants': True})

    def test_discover_propagates_exception(self):
        self.discovery.client.backups.list = (
            self.cinder_client_exception)

        self.assertRaises(
            cinder_exceptions.ClientException,
            self.discovery.discover, self.manager)


class TestVolumePoolsDiscovery(_BaseDiscoveryTestCase):

    def setUp(self):
        super().setUp()
        self.discovery = discovery.VolumePoolsDiscovery(self.CONF)

    def test_discover_returns_pools(self):
        resources = self.discovery.discover(self.manager)

        self.assertEqual(fakes.POOL_LIST, resources)

    def test_discover_empty(self):
        self.discovery.client.pools.list = mock.Mock(return_value=[])

        resources = self.discovery.discover(self.manager)

        self.assertEqual([], resources)

    def test_discover_calls_list_pools_with_detailed_true(self):
        with mock.patch.object(
            self.discovery.client.pools, 'list',
            wraps=self.discovery.client.pools.list
        ) as spy:

            self.discovery.discover(self.manager)

            spy.assert_called_once_with(detailed=True)

    def test_discover_propagates_exception(self):
        self.discovery.client.pools.list = (
            self.cinder_client_exception)

        self.assertRaises(
            cinder_exceptions.ClientException,
            self.discovery.discover, self.manager)


class TestVolumeServicesDiscovery(_BaseDiscoveryTestCase):

    def setUp(self):
        super().setUp()
        self.discovery = discovery.VolumeServicesDiscovery(self.CONF)

    def test_discover_returns_services(self):
        resources = self.discovery.discover(self.manager)

        self.assertEqual(fakes.SERVICE_LIST, resources)

    def test_discover_empty(self):
        self.discovery.client.services.list = mock.Mock(
            return_value=[])

        resources = self.discovery.discover(self.manager)

        self.assertEqual([], resources)

    def test_discover_calls_list_services_with_no_args(self):
        with mock.patch.object(
            self.discovery.client.services, 'list',
            wraps=self.discovery.client.services.list
        ) as spy:

            self.discovery.discover(self.manager)

            spy.assert_called_once_with()

    def test_discover_propagates_exception(self):
        self.discovery.client.services.list = (
            self.cinder_client_exception)

        self.assertRaises(
            cinder_exceptions.ClientException,
            self.discovery.discover, self.manager)
