# Copyright 2025 Red Hat, Inc
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
from keystoneauth1.access import service_catalog
from keystoneauth1 import exceptions as ka_exceptions
from keystoneauth1.exceptions import catalog as catalog_exceptions
from keystoneclient import exceptions as ks_exceptions
from oslo_config import cfg
from oslo_config import fixture as config_fixture

from ceilometer import keystone_client
from ceilometer import service as ceilo_service
from ceilometer.tests import base
from ceilometer.tests.unit import fakes

CONF = cfg.CONF


class FakeSession:
    """A fake keystone auth session."""
    pass


class FakeAuthPlugin:
    """A fake keystone Auth Plugin."""
    pass


class TestKeystoneClient(base.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.CONF = ceilo_service.prepare_service([], [])
        # V3 catalog format
        catalog_data = [
            {
                'type': 'compute',
                'name': 'nova',
                'endpoints': [
                    {
                        'region_id': 'RegionOne',
                        'interface': 'public',
                        'url': 'http://nova.public/v2.1'
                    },
                    {
                        'region_id': 'RegionOne',
                        'interface': 'internal',
                        'url': 'http://nova.internal/v2.1'
                    },
                ]
            },
            {
                'type': 'identity',
                'name': 'keystone',
                'endpoints': [
                    {
                        'region_id': 'RegionOne',
                        'interface': 'public',
                        'url': 'http://keystone.public/v3'
                    },
                ]
            },
            {
                'type': 'network',
                'name': 'neutron',
                'endpoints': [
                    {
                        'region_id': 'RegionOne',
                        'interface': 'public',
                        'url': 'http://neutron.public'
                    }
                ]
            },
            {
                'type': 'radosgw',
                'name': 'radosgw',
                'endpoints': [
                    {
                        'region_id': 'RegionOne',
                        'interface': 'public',
                        'url': 'http://radosgw.public'
                    }
                ]
            },
            {
                'type': 'radosgw',
                'name': 'swift',
                'endpoints': [
                    {
                        'region_id': 'RegionOne',
                        'interface': 'public',
                        'url': 'http://swift.public'
                    }
                ]
            }
        ]
        self.fake_catalog = service_catalog.ServiceCatalogV3(catalog_data)

    @mock.patch(
        'keystoneauth1.loading.load_session_from_conf_options',
        return_value=FakeSession(), autospec=True)
    @mock.patch(
        'keystoneauth1.loading.load_auth_from_conf_options',
        return_value=FakeAuthPlugin(), autospec=True)
    def test_get_session(self, mock_load_auth, mock_load_session):

        session = keystone_client.get_session(self.CONF)

        mock_load_auth.assert_called_once_with(
            self.CONF, keystone_client.DEFAULT_GROUP)
        mock_load_session.assert_called_once_with(
            self.CONF, keystone_client.DEFAULT_GROUP,
            auth=mock_load_auth.return_value, session=None)
        self.assertIsInstance(session, FakeSession)

    @mock.patch(
        'keystoneauth1.loading.load_session_from_conf_options',
        return_value=FakeSession(), autospec=True)
    @mock.patch(
        'keystoneauth1.loading.load_auth_from_conf_options',
        return_value=FakeAuthPlugin(), autospec=True)
    def test_get_session_with_group(self, mock_load_auth, mock_load_session):

        session = keystone_client.get_session(
            self.CONF, group="some_other_group")

        mock_load_auth.assert_called_once_with(self.CONF, "some_other_group")
        mock_load_session.assert_called_once_with(
            self.CONF, "some_other_group",
            auth=mock_load_auth.return_value, session=None)
        self.assertIsInstance(session, FakeSession)

    @mock.patch(
        'keystoneauth1.loading.load_session_from_conf_options',
        return_value=FakeSession(), autospec=True)
    @mock.patch(
        'keystoneauth1.loading.load_auth_from_conf_options',
        return_value=FakeAuthPlugin(), autospec=True)
    def test_get_session_with_session(self, mock_load_auth, mock_load_session):
        fakeSession = FakeSession()

        session = keystone_client.get_session(self.CONF, fakeSession)

        mock_load_auth.assert_called_once_with(
            self.CONF, keystone_client.DEFAULT_GROUP)
        mock_load_session.assert_called_once_with(
            self.CONF, keystone_client.DEFAULT_GROUP,
            auth=mock_load_auth.return_value, session=fakeSession)
        self.assertIsInstance(session, FakeSession)

    @mock.patch(
        'keystoneauth1.loading.load_session_from_conf_options',
        return_value=FakeSession(), autospec=True)
    @mock.patch(
        'keystoneauth1.loading.load_auth_from_conf_options',
        return_value=FakeAuthPlugin(), autospec=True)
    def test_get_session_with_timeout(self, mock_load_auth, mock_load_session):

        session = keystone_client.get_session(self.CONF, timeout=100)

        mock_load_auth.assert_called_once_with(
            self.CONF, keystone_client.DEFAULT_GROUP)
        mock_load_session.assert_called_once_with(
            self.CONF, keystone_client.DEFAULT_GROUP,
            auth=mock_load_auth.return_value, session=None, timeout=100)
        self.assertIsInstance(session, FakeSession)

    @mock.patch('ceilometer.keystone_client.get_session', autospec=True)
    def test_get_connection(self, mock_get_session):
        actual_conn = keystone_client.get_connection(self.CONF)

        mock_get_session.assert_called_once_with(
            self.CONF,
            requests_session=None,
            group=keystone_client.DEFAULT_GROUP)
        self.fake_conn_class_mock.assert_called_once_with(
            session=mock_get_session.return_value,
            oslo_conf=self.CONF,
            service_types={"identity"})
        self.assertEqual(actual_conn, self.fake_conn)

    @mock.patch('ceilometer.keystone_client.get_session', autospec=True)
    def test_get_connection_service_type(self, mock_get_session):
        actual_conn = keystone_client.get_connection(
            self.CONF, service_type="other_service_type")

        mock_get_session.assert_called_once_with(
            self.CONF,
            requests_session=None,
            group=keystone_client.DEFAULT_GROUP)
        self.fake_conn_class_mock.assert_called_once_with(
            session=mock_get_session.return_value,
            oslo_conf=self.CONF,
            service_types={"other_service_type"})
        self.assertEqual(actual_conn, self.fake_conn)

    @mock.patch('ceilometer.keystone_client.get_session', autospec=True)
    def test_get_connection_existing_session(self, mock_get_session):
        mock_session = mock.Mock()

        actual_conn = keystone_client.get_connection(
            self.CONF, requests_session=mock_session)

        mock_get_session.assert_called_once_with(
            self.CONF,
            requests_session=mock_session,
            group=keystone_client.DEFAULT_GROUP)
        self.fake_conn_class_mock.assert_called_once_with(
            session=mock_get_session.return_value,
            oslo_conf=self.CONF,
            service_types={"identity"})
        self.assertEqual(actual_conn, self.fake_conn)

    @mock.patch('ceilometer.keystone_client.get_session', autospec=True)
    def test_get_connection_new_group(self, mock_get_session):

        actual_conn = keystone_client.get_connection(
            self.CONF, group="some_group")

        mock_get_session.assert_called_once_with(
            self.CONF,
            requests_session=None,
            group="some_group")
        self.fake_conn_class_mock.assert_called_once_with(
            session=mock_get_session.return_value,
            oslo_conf=self.CONF,
            service_types={"identity"})
        self.assertEqual(actual_conn, self.fake_conn)

    @mock.patch('ceilometer.keystone_client.get_session', autospec=True)
    def test_get_client(self, mock_get_session):
        mock_session = FakeSession()
        mock_get_session.return_value = mock_session
        conf = self.useFixture(config_fixture.Config(self.CONF))
        conf.config(group=keystone_client.DEFAULT_GROUP, interface="internal")
        conf.config(
            group=keystone_client.DEFAULT_GROUP,
            region_name="expected_region")

        mock_ks = mock.Mock(wraps=fakes.FakeKeystoneClient(
            domains=[], projects=[]))

        mock_ks_cls = self.useFixture(fixtures.MockPatch(
            'keystoneclient.v3.client.Client',
            return_value=mock_ks))

        result = keystone_client.get_client(conf.conf)

        self.assertIsInstance(result, keystone_client.Client)
        mock_get_session.assert_called_once_with(
            self.CONF,
            requests_session=None,
            group=keystone_client.DEFAULT_GROUP)
        mock_ks_cls.mock.assert_called_once_with(
            session=mock_get_session.return_value,
            interface="internal",
            region_name="expected_region")

    def test_get_service_catalog(self):
        mock_client = mock.Mock()
        mock_catalog = [
            {'name': 'keystone', 'type': 'identity'},
            {'name': 'nova', 'type': 'compute'}
        ]
        mock_access = mock.Mock()
        mock_access.service_catalog = mock_catalog
        mock_client.session.auth.get_access.return_value = mock_access

        result = keystone_client.get_service_catalog(mock_client)

        mock_client.session.auth.get_access.assert_called_once_with(
            mock_client.session)
        self.assertEqual(result, mock_catalog)

    def test_get_service_catalog_with_real_client(self):
        mock_session = mock.Mock()
        client = keystone_client.Client(session=mock_session)

        result = keystone_client.get_service_catalog(client)

        mock_session.auth.get_access.assert_called_once_with(mock_session)
        self.assertEqual(
            result, mock_session.auth.get_access.return_value.service_catalog)

    def test_get_auth_token_with_real_client(self):
        mock_session = mock.Mock()
        client = keystone_client.Client(session=mock_session)

        result = keystone_client.get_auth_token(client)

        mock_session.auth.get_access.assert_called_once_with(mock_session)
        self.assertEqual(
            result, mock_session.auth.get_access.return_value.auth_token)

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_url_for(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        url = keystone_client.url_for(mock.Mock())

        self.assertEqual(url, "http://nova.public/v2.1")

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_url_for_service_type(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        url = keystone_client.url_for(mock.Mock(), service_type="network")

        self.assertEqual(url, "http://neutron.public")

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_url_for_service_name(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        url = keystone_client.url_for(mock.Mock(), service_name="neutron")

        self.assertEqual(url, "http://neutron.public")

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_url_for_service_name_and_type_agree(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        url = keystone_client.url_for(
            mock.Mock(),
            service_type="compute",
            service_name="nova")

        self.assertEqual(url, "http://nova.public/v2.1")

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_url_for_service_name_and_type_disagree(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        self.assertRaises(
            catalog_exceptions.EndpointNotFound,
            keystone_client.url_for,
            mock.Mock(),
            service_type="network",
            service_name="nova")

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_url_for_non_existant_service(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        self.assertRaises(
            catalog_exceptions.EndpointNotFound,
            keystone_client.url_for,
            mock.Mock(),
            service_type="rating")

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_url_for_interface(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        url = keystone_client.url_for(mock.Mock(), interface="public")

        self.assertEqual(url, "http://nova.public/v2.1")

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_url_for_region_name(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        url = keystone_client.url_for(
            mock.Mock(),
            region_name="RegionOne")

        self.assertEqual(url, "http://nova.public/v2.1")

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_url_for_region_name_non_existant(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        self.assertRaises(
            catalog_exceptions.EndpointNotFound,
            keystone_client.url_for,
            mock.Mock(),
            region_name="UnknownRegion")

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_url_for_interface_internal(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        url = keystone_client.url_for(
            mock.Mock(),
            service_type="compute",
            interface="internal")

        self.assertEqual(url, "http://nova.internal/v2.1")

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_url_for_interface_non_existant(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        self.assertRaises(
            catalog_exceptions.EndpointNotFound,
            keystone_client.url_for,
            mock.Mock(),
            service_type="network",
            interface="internal")

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_url_for_service_type_and_interface(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        url = keystone_client.url_for(
            mock.Mock(),
            service_type="identity",
            interface="public")

        self.assertEqual(url, "http://keystone.public/v3")

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_url_for_empty_catalog(self, mock_get_catalog):
        mock_get_catalog.return_value = service_catalog.ServiceCatalogV3([])

        self.assertRaises(
            catalog_exceptions.EndpointNotFound,
            keystone_client.url_for,
            mock.Mock(),
            service_type="compute")

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_url_for_service_type_multiple_matches(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        url = keystone_client.url_for(
            mock.Mock(),
            service_type="radosgw")

        self.assertEqual(url, "http://radosgw.public")

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_url_for_service_name_service_type_multi_match(
            self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        url = keystone_client.url_for(
            mock.Mock(),
            service_type="radosgw",
            service_name="swift")

        self.assertEqual(url, "http://swift.public")

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_url_for_calls_get_service_catalog(self, mock_get_catalog):
        mock_catalog = mock.Mock()
        mock_catalog.url_for.return_value = "http://test.url"
        mock_get_catalog.return_value = mock_catalog
        mock_client = mock.Mock()

        result = keystone_client.url_for(
            mock_client,
            service_type="compute",
            service_name="nova",
            interface="public",
            region_name="RegionOne")

        mock_get_catalog.assert_called_once_with(mock_client)
        mock_catalog.url_for.assert_called_once_with(
            service_type="compute",
            service_name="nova",
            interface="public",
            region_name="RegionOne")
        self.assertEqual(result, "http://test.url")

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_get_urls(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        urls = keystone_client.get_urls(
            mock.Mock(),
            service_type="compute",
            interface="public")

        self.assertEqual(urls, ("http://nova.public/v2.1",))

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_get_urls_service_type(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        urls = keystone_client.get_urls(
            mock.Mock(),
            service_type="network",
            interface="public")

        self.assertEqual(urls, ("http://neutron.public",))

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_get_urls_service_name(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        urls = keystone_client.get_urls(
            mock.Mock(),
            service_name="neutron",
            interface="public")

        self.assertEqual(urls, ("http://neutron.public",))

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_get_urls_service_name_and_type_agree(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        urls = keystone_client.get_urls(
            mock.Mock(),
            service_type="compute",
            service_name="nova",
            interface="public")

        self.assertEqual(urls, ("http://nova.public/v2.1",))

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_get_urls_service_name_and_type_disagree(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        urls = keystone_client.get_urls(
            mock.Mock(),
            service_type="network",
            service_name="nova",
            interface="public")

        self.assertEqual(urls, ())

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_get_urls_non_existant_service(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        urls = keystone_client.get_urls(
            mock.Mock(),
            service_type="rating",
            interface="public")

        self.assertEqual(urls, ())

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_get_urls_interface(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        urls = keystone_client.get_urls(
            mock.Mock(),
            service_type="compute",
            interface="public")

        self.assertEqual(urls, ("http://nova.public/v2.1",))

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_get_urls_region_name(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        urls = keystone_client.get_urls(
            mock.Mock(),
            service_type="compute",
            interface="public",
            region_name="RegionOne")

        self.assertEqual(urls, ("http://nova.public/v2.1",))

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_get_urls_region_name_non_existant(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        urls = keystone_client.get_urls(
            mock.Mock(),
            service_type="compute",
            interface="public",
            region_name="UnknownRegion")

        self.assertEqual(urls, ())

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_get_urls_interface_internal(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        urls = keystone_client.get_urls(
            mock.Mock(),
            service_type="compute",
            interface="internal")

        self.assertEqual(urls, ("http://nova.internal/v2.1",))

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_get_urls_interface_non_existant(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        urls = keystone_client.get_urls(
            mock.Mock(),
            service_type="network",
            interface="internal")

        self.assertEqual(urls, ())

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_get_urls_service_type_and_interface(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        urls = keystone_client.get_urls(
            mock.Mock(),
            service_type="identity",
            interface="public")

        self.assertEqual(urls, ("http://keystone.public/v3",))

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_get_urls_empty_catalog(self, mock_get_catalog):
        mock_get_catalog.return_value = service_catalog.ServiceCatalogV3([])

        urls = keystone_client.get_urls(
            mock.Mock(),
            service_type="compute",
            interface="public")

        self.assertEqual(urls, ())

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_get_urls_service_type_multiple_matches(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        urls = keystone_client.get_urls(
            mock.Mock(),
            service_type="radosgw")

        self.assertEqual(
            urls,
            ("http://radosgw.public", "http://swift.public"))

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_get_urls_service_name_service_type_multi(self, mock_get_catalog):
        mock_get_catalog.return_value = self.fake_catalog

        urls = keystone_client.get_urls(
            mock.Mock(),
            service_type="radosgw",
            service_name="swift")

        self.assertEqual(
            urls, ("http://swift.public",))

    @mock.patch(
        'ceilometer.keystone_client.get_service_catalog', autospec=True)
    def test_get_urls_calls_get_service_catalog(self, mock_get_catalog):
        mock_catalog = mock.Mock()
        mock_catalog.get_urls.return_value = ["http://test.url"]
        mock_get_catalog.return_value = mock_catalog
        mock_client = mock.Mock()

        result = keystone_client.get_urls(
            mock_client,
            service_type="compute",
            service_name="nova",
            interface="public",
            region_name="RegionOne")

        mock_get_catalog.assert_called_once_with(mock_client)
        mock_catalog.get_urls.assert_called_once_with(
            service_type="compute",
            service_name="nova",
            interface="public",
            region_name="RegionOne")
        self.assertEqual(result, ["http://test.url"])

    def test_get_auth_token(self):
        mock_client = mock.Mock()
        mock_access = mock.Mock()
        mock_access.auth_token = 'auth_token'
        mock_client.session.auth.get_access.return_value = mock_access

        result = keystone_client.get_auth_token(mock_client)

        mock_client.session.auth.get_access.assert_called_once_with(
            mock_client.session)
        self.assertIsInstance(result, str)
        self.assertEqual(result, 'auth_token')

    def test_get_auth_token_from_openstacksdk_connection(self):
        self.fake_conn.session = mock.Mock()
        mock_access = mock.Mock()
        mock_access.auth_token = 'my_connection_auth_token'
        self.fake_conn.session.auth.get_access.return_value = mock_access

        result = keystone_client.get_auth_token(self.fake_conn)

        self.fake_conn.session.auth.get_access.assert_called_once_with(
            self.fake_conn.session)
        self.assertIsInstance(result, str)
        self.assertEqual(result, 'my_connection_auth_token')


class TestKeystoneClientClientClass(base.BaseTestCase):

    def setUp(self):
        super().setUp()
        domains = fakes.DEFAULT_DOMAINS + [fakes.DOMAIN_DISABLED]

        self.fake_ks = fakes.FakeKeystoneClient(domains=domains)
        self.useFixture(fixtures.MockPatch(
            'keystoneclient.v3.client.Client',
            return_value=self.fake_ks))
        self.client = keystone_client.Client(session=mock.Mock())

    def test_find_project(self):
        result = self.client.find_project(name='admin')
        self.assertEqual(fakes.PROJECT_ADMIN, result)

    def test_find_project_not_found(self):
        self.assertRaises(
            ka_exceptions.NotFound,
            self.client.find_project,
            name='nonexistent')

    def test_find_project_not_found_message(self):
        try:
            self.client.find_project(name='nonexistant')
        except ka_exceptions.NotFound as e:
            self.assertEqual(
                e.details,
                "No Project matching {'name': 'nonexistant'}.")

    def test_find_project_no_unique_match(self):
        fake_ks = fakes.FakeKeystoneClient(
            domains=[],
            projects=[fakes.PROJECT_ADMIN, fakes.PROJECT_ADMIN])
        with mock.patch('keystoneclient.v3.client.Client',
                        return_value=fake_ks):
            client = keystone_client.Client(session=mock.Mock())
        self.assertRaises(
            ks_exceptions.NoUniqueMatch,
            client.find_project,
            name='admin')

    def test_find_project_no_unique_match_message(self):
        fake_ks = fakes.FakeKeystoneClient(
            domains=[],
            projects=[fakes.PROJECT_ADMIN, fakes.PROJECT_ADMIN])
        with mock.patch('keystoneclient.v3.client.Client',
                        return_value=fake_ks):
            client = keystone_client.Client(session=mock.Mock())
        self.assertRaisesRegex(
            ks_exceptions.NoUniqueMatch,
            "ClientException",
            client.find_project,
            name='admin')

    def test_list_projects(self):
        result = self.client.list_projects(fakes.DOMAIN_DEFAULT)
        self.assertEqual(
            [fakes.PROJECT_ADMIN, fakes.PROJECT_SERVICE,
                fakes.PROJECT_DISABLED],
            result)

    def test_list_projects_domain_id(self):
        result = self.client.list_projects(fakes.DOMAIN_DEFAULT.id)

        self.assertEqual(
            [fakes.PROJECT_ADMIN, fakes.PROJECT_SERVICE,
                fakes.PROJECT_DISABLED],
            result)

    def test_list_projects_filter_enabled(self):
        result = self.client.list_projects(
            fakes.DOMAIN_DEFAULT.id, enabled=True)
        self.assertEqual([fakes.PROJECT_ADMIN, fakes.PROJECT_SERVICE], result)

    def test_list_projects_no_match(self):
        # Use a domain that none of the projects belong to
        result = self.client.list_projects(fakes.DOMAIN_DISABLED)
        self.assertEqual([], result)
