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

    def test_get_auth_token(self):
        mock_client = mock.Mock()
        mock_access = mock.Mock()
        mock_access.auth_token = 'auth_token'
        mock_client.session.auth.get_access.return_value = mock_access

        result = keystone_client.get_auth_token(mock_client)

        mock_client.session.auth.get_access.assert_called_once_with(
            mock_client.session)
        self.assertEqual(result, 'auth_token')
