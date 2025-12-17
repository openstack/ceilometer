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

from keystoneauth1.access import service_catalog
from keystoneauth1.exceptions import catalog as catalog_exceptions
from oslo_config import cfg
from oslo_config import fixture as config_fixture

from ceilometer import keystone_client
from ceilometer import service as ceilo_service
from ceilometer.tests import base

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

    @mock.patch('keystoneclient.v3.client.Client', autospec=True)
    @mock.patch('ceilometer.keystone_client.get_session', autospec=True)
    def test_get_client(self, mock_get_session, mock_ks_client):
        mock_session = FakeSession()
        mock_get_session.return_value = mock_session
        mock_client = mock.Mock()
        mock_ks_client.return_value = mock_client
        conf = self.useFixture(config_fixture.Config(self.CONF))
        conf.config(group=keystone_client.DEFAULT_GROUP, interface="internal")
        conf.config(
            group=keystone_client.DEFAULT_GROUP,
            region_name="expected_region")

        result = keystone_client.get_client(conf.conf)

        mock_get_session.assert_called_once_with(
            self.CONF,
            requests_session=None,
            group=keystone_client.DEFAULT_GROUP)
        mock_ks_client.assert_called_once_with(
            session=mock_get_session.return_value,
            trust_id=None,
            interface="internal",
            region_name="expected_region")
        self.assertEqual(result, mock_client)

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
        self.assertEqual(result, 'auth_token')
